# print("Iniciando processamento do gpkg_1.py...")

import os
import re
import zipfile
import sqlite3
import xml.etree.ElementTree as ET

from qgis.core import (
    QgsVectorLayer, QgsProject, QgsVectorFileWriter, QgsField, QgsFeature,
    QgsGeometry, QgsPointXY, QgsMarkerSymbol, QgsRasterMarkerSymbolLayer,
    QgsLineSymbol, QgsSimpleLineSymbolLayer, QgsFillSymbol, QgsSimpleFillSymbolLayer,
    QgsSingleSymbolRenderer
)
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QColor

# ---------------- Utilitários ----------------

def sanitize_layer_name(name):
    if not name:
        return "no_name"
    name = name.strip()
    name = re.sub(r'[^\w\s\-\u00C0-\u017F]', '_', name) # Limita a apenas letras acentuadas latinas
    return name[:60]

def parse_coords_text(coords_text):
    pts = []
    # alt = []
    alt = None
    if not coords_text:
        return pts
    for c in coords_text.strip().split():
        parts = c.split(',')
        if len(parts) < 2:
            continue
        # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)
        x = float(parts[0]); y = float(parts[1]); z = float(parts[2]) if len(parts) >= 3 else 0.0
        pts.append(QgsPointXY(x, y))
        alt = z #if alt is None else alt

    return pts, alt # if alt != [] else None

def extract_simpledata_placemark(pm, ns):
    # Extrai os dados do SimpleData,
    # exceto pdfmaps_photos, 
    # e retorna um dicionário de atributos
    attrs = {}
    for sd in pm.findall(".//kml:SchemaData/kml:SimpleData", ns):
        field_name = sd.attrib.get("name")
        value = (sd.text or "").strip()
        if field_name and field_name != "pdfmaps_photos":
            attrs[field_name] = value
    return attrs

def extract_pdfmaps_photos(pm, ns):
    # Extrai nomes de fotos do campo pdfmaps_photos 
    # e retorna como string separada por ';'
    sd = pm.find(".//kml:SchemaData/kml:SimpleData[@name='pdfmaps_photos']", ns)
    if sd is None or not sd.text:
        return None
    raw = sd.text
    pattern = re.compile(r'images/([^"\'>]+\.(?:jpg|jpeg|png|gif))', re.IGNORECASE)
    nomes = pattern.findall(raw)
    if not nomes:
        return None
    seen = set() # TODO: Confirmar necessidade disso!
    out = []
    for n in nomes:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return ";".join(out)

# -------- Extração de geometrias:
# def extract_point(pm, ns):
#     el = pm.find(".//kml:Point/kml:coordinates", ns)
#     if el is None or (el.text or "").strip() == "":
#         return None, None
#     pts, alt = parse_coords_text(el.text)
#     return QgsGeometry.fromPointXY(pts[0]) if pts else None, alt # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)

# def extract_linestring(pm, ns):
#     el = pm.find(".//kml:LineString/kml:coordinates", ns)
#     if el is None or (el.text or "").strip() == "":
#         return None
#     pts, _ = parse_coords_text(el.text)
#     return QgsGeometry.fromPolylineXY(pts) if pts else None

# def extract_polygon(pm, ns):
#     el = pm.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
#     if el is None or (el.text or "").strip() == "":
#         return None
#     pts, _ = parse_coords_text(el.text)
#     if not pts:
#         return None
#     if pts[0] != pts[-1]:
#         pts.append(pts[0])
#     return QgsGeometry.fromPolygonXY([pts])

# def extract_track_with_point_attributes(pm, ns, gx):
    
#     track = pm.find(".//gx:Track", gx)
#     if track is None:
#         return None, [], None  # Condição de erro de formato no kml
#     whens = track.findall("gx:when", gx)
#     coords = track.findall("gx:coord", gx)
#     # TODO: Verificar necessidade de adicionar <gx:angles>
#     angles = track.findall("gx:angles", gx)
#     arrays = {}
#     for sad in track.findall(".//gx:SimpleArrayData", gx):
#         name = sad.attrib.get("name")
#         values = [ (v.text or "").strip() for v in sad.findall("gx:value", gx) ]
#         if name:
#             arrays[name] = values
#     pts = []
#     point_feats = []
#     alt = []
#     for i, c in enumerate(coords):
#         txt = (c.text or "").strip()
#         if not txt:
#             continue # Condição de erro de formato no kml
#         parts = txt.split()
#         if len(parts) < 2:
#             continue # Condição de erro de formato no kml
#         x = float(parts[0]); y = float(parts[1])
#         z = float(parts[2]) if len(parts) >= 3 else None # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)
#         pt = QgsPointXY(x, y)
#         pts.append(pt)
#         alt.append(z)
#         attrs = {}
#         attrs['icon_href'] = 'dot-and-circle'  # Ícone padrão para TrackPoint
#         if i < len(whens):
#             attrs["when"] = (whens[i].text or "").strip()
#         if i < len(angles):
#             attrs["angles"] = (angles[i].text or "").strip()
#         if i < len(coords):  # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)
#             attrs['altitude'] = z

#         for name, vals in arrays.items():
#             if i < len(vals):
#                 attrs[name] = vals[i]
#         point_feats.append((pt, attrs))
#     line_geom = QgsGeometry.fromPolylineXY(pts) if pts else None
#     return line_geom, point_feats, alt

def extract_point_el(pm):
    el = pm.find(".//kml:coordinates", ns)
    if el is None or (el.text or "").strip() == "":
        return None, None
    pts, alt = parse_coords_text(el.text)
    return QgsGeometry.fromPointXY(pts[0]) if pts else None, alt # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)

def extract_linestring_el(pm):
    el = pm.find(".//kml:coordinates", ns)
    if el is None or (el.text or "").strip() == "":
        return None
    pts, _ = parse_coords_text(el.text)
    return QgsGeometry.fromPolylineXY(pts) if pts else None

def extract_polygon_el(pm):
    el = pm.find(".//kml:coordinates", ns)
    if el is None or (el.text or "").strip() == "":
        return None
    pts, _ = parse_coords_text(el.text)
    if not pts:
        return None
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return QgsGeometry.fromPolygonXY([pts])

def extract_track_with_point_attributes_el(track):
    
    # track = track.find(".//gx:Track", gx)
    if track is None:
        return None, [], None # Condição de erro de formato no kml
    whens = track.findall("kml:when", ns)
    coords = track.findall("gx:coord", gx)
    # TODO: Verificar necessidade de adicionar <gx:angles>
    angles = track.findall("gx:angles", gx)
    arrays = {}
    for sad in track.findall(".//gx:SimpleArrayData", gx):
        name = sad.attrib.get("name")
        values = [ (v.text or "").strip() for v in sad.findall("gx:value", gx) ]
        if name:
            arrays[name] = values
    pts = []
    point_feats = []
    alt = []
    for i, c in enumerate(coords):
        txt = (c.text or "").strip()
        if not txt:
            continue # Condição de erro de formato no kml
        parts = txt.split()
        if len(parts) < 2:
            continue # Condição de erro de formato no kml
        x = float(parts[0]); y = float(parts[1])
        z = float(parts[2]) if len(parts) >= 3 else None # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)
        pt = QgsPointXY(x, y)
        pts.append(pt)
        alt.append(z)
        attrs = {}
        attrs['icon_href'] = 'dot-and-circle' # Ícone padrão para TrackPoint
        if i < len(whens):
            attrs["when"] = (whens[i].text or "").strip()
        if i < len(angles):
            attrs["angles"] = (angles[i].text or "").strip()
        if i < len(coords):  # TODO: Verificar necessidade de adicionar altitude (3ª coordenada)
            attrs['altitude'] = z

        for name, vals in arrays.items():
            if i < len(vals):
                attrs[name] = vals[i]
        point_feats.append((pt, attrs))
    line_geom = QgsGeometry.fromPolylineXY(pts) if pts else None
    return line_geom, point_feats, alt

ns = {"kml": "http://www.opengis.net/kml/2.2"}
gx = {"gx": "http://www.google.com/kml/ext/2.2"}

geometrias = {
            'Point': (extract_point_el), 
            'LineString': (extract_linestring_el), 
            'Polygon': (extract_polygon_el), # 'LinearRing' 
            'Track': (extract_track_with_point_attributes_el)
            }

def handle_geometry_extraction(command, elem_pai='None'):
    action = geometrias.get(command)
    if action:
        return action(elem_pai)
    else:
        return None

# -------- Fim extração de geometrias ---

# ---------------- Estilos KML ----------------

def kml_color_to_qgis(i):
    i = (i or "").strip()
    if len(i) != 8:  # Condição de erro de formato no kml: retorna preto opaco
        return 100, "#000000"
    try:
        opacity = round(int(i[:2], 16) * 100 / 255)
        hex_color = f'#{i[-2:] + i[4:6] + i[2:4]}'
        return opacity, hex_color
    except:  # Condição de erro de formato no kml: retorna preto opaco
        return 100, "#000000"

def parse_styles(root, ns):
    # styles = {}
    styles = []
    # Estilo padrão para o estilo Point de Track
    styles.append({
        'id': 'track',
        # 'icon_href': 'dot-and-circle'
        'icon_href': 'dot-and-circle',
        'line_width': None,
        'line_opacity': None,
        'line_color_hex': None,
        'poly_opacity': None,
        'poly_color_hex': None
    })
    for st in root.findall(".//kml:Style", ns):
        sid = st.attrib.get('id', '') or ''
        if not sid:
            continue # Condição de erro de formato no kml
        icon_href = None
        line_width = None
        line_opacity = None
        line_color_hex = None
        poly_opacity = None
        poly_color_hex = None

        icon_el = st.find(".//kml:IconStyle/kml:Icon/kml:href", ns)
        if icon_el is not None and icon_el.text: # Tem ícone
            # icon_href = icon_el.text.strip()
            icon_href = icon_el.text.strip().split('/')[-1].split('.')[0]  # Apenas o nome do arquivo, sem extensão

        line_color_el = st.find(".//kml:LineStyle/kml:color", ns)
        line_width_el = st.find(".//kml:LineStyle/kml:width", ns)
        if line_color_el is not None and line_color_el.text:
            lo, lh = kml_color_to_qgis(line_color_el.text)
            line_opacity = lo
            line_color_hex = lh
        if line_width_el is not None and line_width_el.text:
            try:
                line_width = float(line_width_el.text.strip())
            except:
                line_width = None

        poly_color_el = st.find(".//kml:PolyStyle/kml:color", ns)
        if poly_color_el is not None and poly_color_el.text:
            po, ph = kml_color_to_qgis(poly_color_el.text)
            poly_opacity = po
            poly_color_hex = ph

        # styles[sid] = {
        styles.append({
            'id': sid,
            'icon_href': icon_href,
            'line_width': line_width,
            'line_opacity': line_opacity,
            'line_color_hex': line_color_hex,
            'poly_opacity': poly_opacity,
            'poly_color_hex': poly_color_hex
        })
    return styles

def extract_styleurl(pm, ns):
    el = pm.find("kml:styleUrl", ns)
    if el is not None and el.text:
        s = el.text.strip()
        if s.startswith("#"):
            return s[1:]
        return s #Retorna o nome do estilo sem o "#"
    return None # Condição de erro de formato no kml

# ---------------- Aplicação de simbologia ----------------

def apply_layer_symbology(layer, gtype, style_info, temp_img_dir):
    icons_dir = os.path.join(os.path.dirname(__file__).replace('/','\\'), 'svg') # Diretório padrão de ícones SVG
    if gtype in ("Point", "TrackPoint"):
        symbol = QgsMarkerSymbol.createSimple({})
        if style_info and style_info.get('icon_href'):
            # href = style_info['icon_href']
            href = style_info['icon_href']
            # icon_path = os.path.join(temp_img_dir, os.path.basename(href))
            icon_path = os.path.join(icons_dir, href + '.svg')  # Usa o diretório de ícones padrão
            if os.path.exists(icon_path):
                raster_layer = QgsRasterMarkerSymbolLayer(icon_path)
                if raster_layer is not None:
                    symbol.changeSymbolLayer(0, raster_layer)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    elif gtype in ("LineString", "TrackLine"):
        symbol = QgsLineSymbol.createSimple({})
        line_layer = QgsSimpleLineSymbolLayer()
        if style_info and style_info.get('line_color_hex'):
            line_layer.setColor(QColor(style_info['line_color_hex']))
        if style_info and style_info.get('line_width') is not None:
            line_layer.setWidth(style_info['line_width'])
        if style_info and style_info.get('line_opacity') is not None:
            symbol.setOpacity(style_info['line_opacity'] / 100.0)
        symbol.changeSymbolLayer(0, line_layer)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    elif gtype == "Polygon":
        # Fill (PolyStyle) e Outline (LineStyle)
        fill_color_hex = style_info.get('poly_color_hex') if style_info else "#000000"
        fill_opacity = (style_info.get('poly_opacity') / 100.0) if (style_info and style_info.get('poly_opacity') is not None) else 1.0
        outline_color_hex = style_info.get('line_color_hex') if style_info else "#000000"
        outline_width = style_info.get('line_width') if (style_info and style_info.get('line_width') is not None) else 0.26
        outline_opacity = (style_info.get('line_opacity') / 100.0) if (style_info and style_info.get('line_opacity') is not None) else 1.0

        # Cria cores com alfa para contorno
        stroke_color = QColor(outline_color_hex)
        stroke_color.setAlphaF(outline_opacity)

        # Para preenchimento, usamos opacidade do símbolo (global do fill)
        symbol = QgsFillSymbol.createSimple({})
        fill_layer = QgsSimpleFillSymbolLayer()
        fill_layer.setFillColor(QColor(fill_color_hex))
        fill_layer.setStrokeColor(stroke_color)
        fill_layer.setStrokeWidth(outline_width)
        fill_layer.setStrokeStyle(Qt.SolidLine)

        symbol.changeSymbolLayer(0, fill_layer)
        symbol.setOpacity(fill_opacity)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

def store_style_attributes_in_layer(layer, style_fields_present, pr):
    needed = []
    def ensure(name):
        if layer.fields().indexOf(name) == -1 and name not in style_fields_present:
            needed.append(QgsField(name, QVariant.String))
            style_fields_present.add(name)
    ensure("Style")
    ensure("icon_href")
    ensure("line_color_hex")
    ensure("line_opacity")
    ensure("line_width_px")
    ensure("poly_color_hex")
    ensure("poly_opacity")
    if needed:
        pr.addAttributes(needed)
        layer.updateFields()

def set_feature_style_attributes(f, layer, style_info):
    # TODO: Deve buscar as características do Style n tabela Styles do GPKG
    if not style_info:
        return
    def setattr(name, value):
        idx = layer.fields().indexOf(name)
        if idx != -1 and value is not None: # Se o campo existir e valor não for None
            f.setAttribute(idx, str(value))
    setattr("Style", style_info)
    # TODO: Confirmar se mantem os atributos abaixo
    # setattr("Style", style_info.get('id')) # ! << AttributeError: 'str' object has no attribute 'get'
    # setattr("icon_href", style_info.get('icon_href'))
    # setattr("line_color_hex", style_info.get('line_color_hex'))
    # setattr("line_opacity", style_info.get('line_opacity'))
    # setattr("line_width_px", style_info.get('line_width'))
    # setattr("poly_color_hex", style_info.get('poly_color_hex'))
    # setattr("poly_opacity", style_info.get('poly_opacity'))

# ---------------- Classe principal ----------------

class Zip_Kmz:
    print("Classe Zip_Kmz sendo definida.")

    def __init__(self, arquivo_kmz):
        self.arquivo_kmz = arquivo_kmz
        self.zip_kmz = zipfile.ZipFile(self.arquivo_kmz, 'r')
        self.root = self.parse_kml()
        self.simbologia = None
        self.point_cols = ['Name', 'geometry', 'Time', 'Style', 'Notes', 'Icon_URL', 'Icon_local']
        self.schema = {}
        # self.folders = self.process_folders()

    def process_folders(self):
        # Processa todos os folders
        folders = []
        for i, folder in enumerate(self.root.findall(".//kml:Folder", ns)):
            folder_name_el = folder.find("kml:name", ns)
            folder_name = folder_name_el.text if folder_name_el is not None else "no_name"
            folder_name = sanitize_layer_name(folder_name)
            print(f"\n\tProcessando folder: {i+1} - {folder_name}")
            # Processa os placemarks dentro do folder
            
            folders.append({'data': self.process_placemarks(folder), 'name': folder_name}) # Processa todos os placemark do folder
        return folders

    def process_placemarks(self, folder):
        # Processa todos os placemark do folder
        placemarks = {
            'Point': [], 
            'LineString': [], 
            'Polygon': [], 
            'Track': []
            }
        for i, pm in enumerate(folder.findall(".//kml:Placemark", ns)):
            name_el = pm.find("kml:name", ns)
            name = name_el.text if name_el is not None else "no_name"
            print(f"\t\tProcessando placemark: {i+1} - {name}")
            placemark = self.get_placemark(pm)
            placemarks[placemark['tipo']].append(placemark) # Processa o placemark atual e extrai nome, atributos, fotos, estilo e geometria
        return placemarks
    
    def get_placemark(self, pm):
            name = pm.find("kml:name", ns).text if pm.find("kml:name", ns) is not None else ""
            attrs_placemark = extract_simpledata_placemark(pm, ns) # Retorna dic de SimpleData, exceto pdfmaps_photos
            photos = extract_pdfmaps_photos(pm, ns) # Retorna string com nomes separados por ";" (ou None)
            style_id = extract_styleurl(pm, ns) # Retorna o nome do estilo sem o "#" (ou None!)
            tipo, coord = self.process_geometria(pm) # Retorna tipo de geometria e coordenadas em texto
            # print(f"\t\t\t-Geometria: {tipo}")
            # print(f"\t\t\t'-coordinates': {coord}")
            return {'name': name, 'attrs': attrs_placemark, 'photos': photos, 'style_id': style_id, 'tipo': tipo, 'coord': coord}

    def process_geometria(self, pm):
        # xpath = './/{' + ns["kml"] + '}coordinates/..'
        xpath = './/{' + ns["kml"] + '}coordinates'
        pai_el = pm.find(xpath + '/..') # Para encontrar o pai do kml:coordinates, que pode ser Point, LineString ou Polygon
        if pai_el is not None:
            tipo = pai_el.tag.split('}')[-1]
            if tipo == 'LinearRing':
                tipo = 'Polygon' # Para tratar LinearRing como Polygon, já que é o que o QGIS espera
        else:
            # xpath = './/{' + gx["gx"] + '}coord/..'
            xpath = './/{' + gx["gx"] + '}coord'
            pai_el = pm.find(xpath + '/..') # Para encontrar o pai do gx:coord, que é o elemento Track
            if pai_el is not None:
                tipo = pai_el.tag.split('}')[-1]
               
                # if pai_el is not None:
                #     coord = pai_el.find(xpath)
                    # coord = coord.text if coord is not None and coord.text else None
            else:
                assert False, "*** Não encontrou elemento pai de coordenadas, formato do KML pode estar diferente do esperado. ***"
        
        return tipo, handle_geometry_extraction(tipo, pai_el)
        # return tipo, handle_geometry_extraction(tipo, coord, gx)

    def process_simbologia(self):
        # Computando as Simbologias:
        self.simbologia = {}
        # for estilo in estilos:
        for estilo in self.root.findall(".//kml:Style", ns):
            parameters = {}
            for i in estilo.iter():
                if i.text:
                    if parameters.get(i.tag.split('}')[1])==None:
                        parameters[i.tag.split('}')[1]] = i.text.strip()
                        if i.tag.split('}')[1]=='color': 
                            # Opacidade em decimal e percentual
                            parameters['opacidade'] = str(round(int(i.text.strip()[:2],16)*100/255))
                            # cor em hexa em RGB
                            parameters['cor'] = f'#{i.text.strip()[-2:] + i.text.strip()[4:6] + i.text.strip()[2:4]}'
                    else:
                        parameters[i.tag.split('}')[1] + '_bg'] = i.text.strip()
                        if i.tag.split('}')[1]=='color':
                            # Opacidade em decimal e percentual
                            parameters['opacidade_bg'] = str(round(int(i.text.strip()[:2],16)*100/255))
                            parameters['cor_bg'] = f'#{i.text.strip()[-2:] + i.text.strip()[4:6] + i.text.strip()[2:4]}'

                else:
                    parameters[i.tag.split('}')[1]] = i.attrib

            self.simbologia[estilo.attrib['id']] = parameters

    def process_schema(self):
        # Computando os schema de Tracks:
        # for esquema in schema:
        for esquema in self.root.findall(".//kml:Schema", ns):
            esquema_dic = {}
            # for campos in esquema.findall(f'.//{ns["kml"]}SimpleArrayField'):
            for campos in esquema.findall(".//gx:SimpleArrayField", gx):
                itens = [(campos.get(i)) for i in campos.keys()]
                esquema_dic[itens[0]] = itens[1]

            for campos in esquema.findall(".//kml:SimpleField", ns):
                itens = [(campos.get(i)) for i in campos.keys()]
                esquema_dic[itens[0]] = itens[1]
            # print(f'\t{esquema.get("name")} (SimpleField): {esquema_dic}')

            self.schema[esquema.get("name")] = esquema_dic
        # Acrescentar colunas de trilha para os df de pontos:
        if self.schema.get('track_schema')!=None:
            self.point_cols = self.point_cols + ['when', 'angles'] + list(self.schema['track_schema'].keys())


    def save_images_to_gpkg(self):
        gpkg_file = self.arquivo_kmz + "_.gpkg"
        gpkg_file = r"C:\TI\Qgis\KML Testes\teste_.gpkg"

        conn = sqlite3.connect(gpkg_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, name TEXT, data BLOB)")
        for nome_arquivo in self.zip_kmz.namelist():
            if nome_arquivo.lower().startswith('images/'):
                with self.zip_kmz.open(nome_arquivo) as imagem_file:
                    blob = imagem_file.read()
                    cur.execute("INSERT INTO images (name, data) VALUES (?, ?)", (os.path.basename(nome_arquivo), blob))
        conn.commit()
        conn.close()

    def save_styles_to_gpkg(self, styles):
        gpkg_file = self.arquivo_kmz + "_.gpkg"
        gpkg_file = r"C:\TI\Qgis\KML Testes\teste_.gpkg"

        conn = sqlite3.connect(gpkg_file)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS styles (
                id INTEGER PRIMARY KEY,
                style_id TEXT,
                icon_href TEXT,
                line_width REAL,
                line_opacity REAL,
                line_color_hex TEXT,
                poly_color_hex TEXT,
                poly_opacity REAL
            )
        """)
        for style in styles:
            cur.execute("""
                INSERT INTO styles (style_id, icon_href, line_width, line_opacity, line_color_hex, poly_color_hex, poly_opacity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                style['id'],
                style['icon_href'],
                style['line_width'],
                style['line_opacity'],
                style['line_color_hex'],
                style['poly_color_hex'],
                style['poly_opacity']
            ))
        conn.commit()
        conn.close()
    def salvar_em_gpkg_2(self):
        # self.save_images() # Salva as imagens na tabela kmz_images
        # self.save_geoms() # Salva as geometrias em camadas organizadas por Folder e tipo de geometria, aplicando simbologia e guardando atributos de estilo
        # self.save_simbologia()

        folder_geom = {}
        # first_layer = True # Pra ver se acrescenta ou cria novo gpkg
        for folder_name, types in folder_geom.items(): # Loop por folders
            for gtype, feats in types.items(): # Loop por tipos de geometria
                if not feats:
                    continue

                if gtype in ("Point", "TrackPoint"):
                    uri = "Point?crs=EPSG:4326"
                elif gtype in ("LineString", "TrackLine"):
                    uri = "LineString?crs=EPSG:4326"
                elif gtype == "Polygon":
                    uri = "Polygon?crs=EPSG:4326"
                else:
                    continue

                layer_name = sanitize_layer_name(f"{folder_name}_{gtype.lower()}")
                layer = QgsVectorLayer(uri, layer_name, "memory")
                pr = layer.dataProvider()
                pr.addAttributes([QgsField("name", QVariant.String)])
                layer.updateFields()

                extra_fields = set()
                needs_photos = False
                style_fields_present = set()
                for _, _, attrs_map, photos, _ in feats: # feats:(name, geom, attrs2(=attrs_placemark), photos2, stinfo)
                    for k in attrs_map.keys():
                        # Addiciona apenas campos que ainda não existem na camada, sem repetir
                        if layer.fields().indexOf(k) == -1 and k not in extra_fields:
                            extra_fields.add(k)
                    if photos:
                        needs_photos = True

                if extra_fields: # Adiciona campos extras em ordem alfabética
                    pr.addAttributes([QgsField(k, QVariant.String) for k in sorted(extra_fields)])
                if needs_photos and layer.fields().indexOf("pdfmaps_photos") == -1:
                    pr.addAttributes([QgsField("pdfmaps_photos", QVariant.String)]) # Adiciona campo de fotos se necessário
                store_style_attributes_in_layer(layer, style_fields_present, pr) # TODO: Verificar necessidade disso
                layer.updateFields()

                qgis_feats = []
                style_info_sample = None
                for name, geom, attrs_map, photos, stinfo in feats: # ! stinfo é pra ser um dic!
                    if geom is None or geom.isEmpty(): # ! Possível inconsistência do KML?
                        continue
                    f = QgsFeature(layer.fields())
                    f.setGeometry(geom)
                    f.setAttribute(layer.fields().indexOf("name"), name)
                    for k, v in attrs_map.items(): # Guarda os valores de cada campo extra, se o campo existir
                        idx = layer.fields().indexOf(k)
                        if idx != -1:
                            f.setAttribute(idx, v)
                    if photos:
                        idx_photos = layer.fields().indexOf("pdfmaps_photos")
                        if idx_photos != -1:
                            f.setAttribute(idx_photos, photos)
                    # Guarda atributos de estilo em campos de estilo, se o campo existir
                    set_feature_style_attributes(f, layer, stinfo) # TODO: Isolado, por enquanto!
                    if style_info_sample is None and stinfo:
                        style_info_sample = stinfo
                    qgis_feats.append(f)

                if qgis_feats:
                    pr.addFeatures(qgis_feats)
                    layer.updateExtents()
                    # TODO: Isolado, por enquanto!
                    # apply_layer_symbology(layer, gtype, style_info_sample, temp_img_dir)

                    options = QgsVectorFileWriter.SaveVectorOptions()
                    options.driverName = "GPKG"
                    options.layerName = layer_name
                    # TODO: Coloquei CreateOrOverwriteLayer direto pra testar, revisar essa lógica
                    # options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                    if first_layer or not os.path.exists(gpkg_path):
                        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
                        first_layer = False
                    else:
                        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

                    err = QgsVectorFileWriter.writeAsVectorFormatV2(
                        layer, gpkg_path, QgsProject.instance().transformContext(), options
                    )
                    if err[0] != QgsVectorFileWriter.NoError:
                        raise Exception(f"Erro ao salvar camada {layer_name} no GeoPackage: {err}")

        # Salva imagens na tabela kmz_images do GeoPackage
        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kmz_images (id INTEGER PRIMARY KEY, name TEXT, data BLOB)")
        for nome_arquivo in self.zip_kmz.namelist():
            if nome_arquivo.lower().startswith('images/'):
                with self.zip_kmz.open(nome_arquivo) as imagem_file:
                    blob = imagem_file.read()
                    cur.execute("INSERT INTO kmz_images (name, data) VALUES (?, ?)", (os.path.basename(nome_arquivo), blob))
        conn.commit()
        conn.close()

        # Salva estilos na tabela Styles no GeoPackage
        styles = parse_styles(root, ns) # Extrai estilos
        # TODO: Exportar estilos em tabela no GPKG para aplicar depois
        # styles[sid] = {
        #     'id': sid,
        #     'icon_href': icon_href,
        #     'line_width': line_width,
        #     'line_opacity': line_opacity,
        #     'line_color_hex': line_color_hex,
        #     'poly_opacity': poly_opacity,
        #     'poly_color_hex': poly_color_hex
        # }

        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        # TODO: Consertar a criação da tabela de estilos
        cur.execute("CREATE TABLE IF NOT EXISTS Styles (id TEXT, icon_href TEXT, line_width INTEGER, line_opacity INTEGER, line_color_hex TEXT, poly_opacity INTEGER, poly_color_hex TEXT)")
        for style in styles:

                    cur.execute("INSERT INTO Styles (id, icon_href, line_width, line_opacity, line_color_hex, poly_opacity, poly_color_hex) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        # (styles[style]['id'], styles[style]['icon_href'], styles[style]['line_width'], styles[style]['line_opacity'], styles[style]['line_color_hex'], styles[style]['poly_opacity'], styles[style]['poly_color_hex']))
                        (style['id'], style['icon_href'], style['line_width'], style['line_opacity'], style['line_color_hex'], style['poly_opacity'], style['poly_color_hex']))
        conn.commit()
        conn.close()

        print(f"GeoPackage criado em: {gpkg_path}")
        print("Camadas por Folder e tipo criadas (inclui TrackLine e TrackPoint).")
        print("Simbologia aplicada conforme Style/styleUrl e campos de estilo gravados.")
        print("Imagens salvas na tabela 'kmz_images' e extraídas para ícones em temp.")
    

    def salvar_em_gpkg(self):
# ---------------- Uso ----------------
# Este script lê um arquivo KMZ do Avenza Maps
# e salva seu conteúdo em um GeoPackage.
# 
# Está guardando na tabela: fid, name, icon_href, line_color_hex, 
# line_opacity, line_width_px, poly_color_hex, poly_opacity, 
# pdfmaps_photos e demais atributos extraídos do SimpleData
# (este último,não confirmei!!!)
#         
        # Extrai todas as feições do KML e salva em um GeoPackage, 
        # organizando por Folder e tipo de geometria, 
        # guardando a simbologia na tabela Styles
        # e as imagens na tabela kmz_images.
        # OBS.: As feições são armazenadas em tabelas com o nome "{folder}_{gtype}",
        # onde gtype é point, linestring, polygon, trackline ou trackpoint.
        # Quando existe algum Folder aninhado, está sendo criada uma tabela para cada Folder
        # com o mesmo conteúdo!!!

        gpkg_path = self.arquivo_kmz + "_.gpkg"

        temp_img_dir = gpkg_path + "_images"
        os.makedirs(temp_img_dir, exist_ok=True)

        # Extrair doc.kml temporariamente
        with self.zip_kmz.open('doc.kml') as kml_file:
            temp_kml = gpkg_path + "_temp.kml"
            with open(temp_kml, "wb") as f:
                f.write(kml_file.read())

        for nome_arquivo in self.zip_kmz.namelist():
            if nome_arquivo.lower().startswith('images/'):
                base = os.path.basename(nome_arquivo)
                out_path = os.path.join(temp_img_dir, base)
                # Extrai a imagem para o diretório temporário
                with self.zip_kmz.open(nome_arquivo) as in_f, open(out_path, "wb") as out_f:
                    out_f.write(in_f.read())

        tree = ET.parse(temp_kml)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        gx = {"gx": "http://www.google.com/kml/ext/2.2"}

        # styles = parse_styles(root, ns) # Extrai estilos
        # TODO: Exportar estilos em tabela no GPKG para aplicar depois

        first_layer = True # Pra ver se acrescenta ou cria novo gpkg
        if os.path.exists(gpkg_path):
            # Abre gpkg e verifica se tem layers
            # TODO: Pede para o usuário confirmar se quer sobreescrever
            pass

        folder_geom = {} # Dic aninhado: folder_name -> gtype -> lista de (name, geom, attrs, photos, style_info)
        for folder in root.findall(".//kml:Folder", ns):
            folder_name = folder.find("kml:name", ns).text if folder.find("kml:name", ns) is not None else "no_name"
            folder_name = sanitize_layer_name(folder_name)
            placemarks = folder.findall(".//kml:Placemark", ns)

            for pm in placemarks:
                name = pm.find("kml:name", ns).text if pm.find("kml:name", ns) is not None else ""
                attrs_placemark = extract_simpledata_placemark(pm, ns) # Retorna dic de SimpleData, exceto pdfmaps_photos
                photos = extract_pdfmaps_photos(pm, ns) # Retorna string com nomes separados por ";" (ou None)
                style_id = extract_styleurl(pm, ns) # Retorna o nome do estilo sem o "#" (ou None!)
                # style_info = styles.get(style_id) if style_id else None # TODO: Revisar essa lógica quando salvar na tabela de estilos

                geoms = []
                # TODO: Quando é um trajeto, mas só tem um ponto, está quebrando!
                # ! >> TypeError: cannot unpack non-iterable NoneType object
                # "C:\TI\Qgis\KML Testes\Avenza\3 camadas.kmz"
                g_point, p_alt = extract_point(pm, ns)
                if p_alt is not None:
                    attrs_placemark['altitude'] = p_alt
                # if g_point: geoms.append(("Point", g_point, attrs_placemark, photos, style_info))
                if g_point: geoms.append(("Point", g_point, attrs_placemark, photos, style_id))

                g_line = extract_linestring(pm, ns)
                # if g_line: geoms.append(("LineString", g_line, attrs_placemark, photos, style_info))
                if g_line: geoms.append(("LineString", g_line, attrs_placemark, photos, style_id))

                g_poly = extract_polygon(pm, ns)
                # if g_poly: geoms.append(("Polygon", g_poly, attrs_placemark, photos, style_info))
                if g_poly: geoms.append(("Polygon", g_poly, attrs_placemark, photos, style_id))

                line_geom, point_feats, t_alt = extract_track_with_point_attributes(pm, ns, gx)
                if line_geom:
                    # geoms.append(("TrackLine", line_geom, attrs_placemark, photos, style_info))
                    geoms.append(("TrackLine", line_geom, attrs_placemark, photos, style_id))
                if point_feats:
                    for pt, per_point_attrs in point_feats:
                        g = QgsGeometry.fromPointXY(pt)
                        merged = dict(attrs_placemark)
                        merged.update(per_point_attrs)
                        # geoms.append(("TrackPoint", g, merged, photos, style_info))
                        # geoms.append(("TrackPoint", g, merged, photos, style_id)) # TODO: TrackPoint deve ter um estilo próprio!!
                        geoms.append(("TrackPoint", g, merged, photos, 'track')) # TODO: TrackPoint deve ter um estilo próprio!!

                for gtype, geom, attrs2, photos2, stinfo in geoms:
                    # Cria um dic aninhado: folder_name -> gtype -> lista de (name, geom, attrs, photos, style_info)
                    # Se não existir, cria os dics intermediários, se existir, apenas adiciona na lista
                    folder_geom.setdefault(folder_name, {}).setdefault(gtype, []).append(
                        (name, geom, attrs2, photos2, stinfo)
                    )

        # first_layer = True # Pra ver se acrescenta ou cria novo gpkg
        for folder_name, types in folder_geom.items(): # Loop por folders
            for gtype, feats in types.items(): # Loop por tipos de geometria
                if not feats:
                    continue

                if gtype in ("Point", "TrackPoint"):
                    uri = "Point?crs=EPSG:4326"
                elif gtype in ("LineString", "TrackLine"):
                    uri = "LineString?crs=EPSG:4326"
                elif gtype == "Polygon":
                    uri = "Polygon?crs=EPSG:4326"
                else:
                    continue

                layer_name = sanitize_layer_name(f"{folder_name}_{gtype.lower()}")
                layer = QgsVectorLayer(uri, layer_name, "memory")
                pr = layer.dataProvider()
                pr.addAttributes([QgsField("name", QVariant.String)])
                layer.updateFields()

                extra_fields = set()
                needs_photos = False
                style_fields_present = set()
                for _, _, attrs_map, photos, _ in feats: # feats:(name, geom, attrs2(=attrs_placemark), photos2, stinfo)
                    for k in attrs_map.keys():
                        # Addiciona apenas campos que ainda não existem na camada, sem repetir
                        if layer.fields().indexOf(k) == -1 and k not in extra_fields:
                            extra_fields.add(k)
                    if photos:
                        needs_photos = True

                if extra_fields: # Adiciona campos extras em ordem alfabética
                    pr.addAttributes([QgsField(k, QVariant.String) for k in sorted(extra_fields)])
                if needs_photos and layer.fields().indexOf("pdfmaps_photos") == -1:
                    pr.addAttributes([QgsField("pdfmaps_photos", QVariant.String)]) # Adiciona campo de fotos se necessário
                store_style_attributes_in_layer(layer, style_fields_present, pr) # TODO: Verificar necessidade disso
                layer.updateFields()

                qgis_feats = []
                style_info_sample = None
                for name, geom, attrs_map, photos, stinfo in feats: # ! stinfo é pra ser um dic!
                    if geom is None or geom.isEmpty(): # ! Possível inconsistência do KML?
                        continue
                    f = QgsFeature(layer.fields())
                    f.setGeometry(geom)
                    f.setAttribute(layer.fields().indexOf("name"), name)
                    for k, v in attrs_map.items(): # Guarda os valores de cada campo extra, se o campo existir
                        idx = layer.fields().indexOf(k)
                        if idx != -1:
                            f.setAttribute(idx, v)
                    if photos:
                        idx_photos = layer.fields().indexOf("pdfmaps_photos")
                        if idx_photos != -1:
                            f.setAttribute(idx_photos, photos)
                    # Guarda atributos de estilo em campos de estilo, se o campo existir
                    set_feature_style_attributes(f, layer, stinfo) # TODO: Isolado, por enquanto!
                    if style_info_sample is None and stinfo:
                        style_info_sample = stinfo
                    qgis_feats.append(f)

                if qgis_feats:
                    pr.addFeatures(qgis_feats)
                    layer.updateExtents()
                    # TODO: Isolado, por enquanto!
                    # apply_layer_symbology(layer, gtype, style_info_sample, temp_img_dir)

                    options = QgsVectorFileWriter.SaveVectorOptions()
                    options.driverName = "GPKG"
                    options.layerName = layer_name
                    # TODO: Coloquei CreateOrOverwriteLayer direto pra testar, revisar essa lógica
                    # options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                    if first_layer or not os.path.exists(gpkg_path):
                        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
                        first_layer = False
                    else:
                        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

                    err = QgsVectorFileWriter.writeAsVectorFormatV2(
                        layer, gpkg_path, QgsProject.instance().transformContext(), options
                    )
                    if err[0] != QgsVectorFileWriter.NoError:
                        raise Exception(f"Erro ao salvar camada {layer_name} no GeoPackage: {err}")

        # Salva imagens na tabela kmz_images do GeoPackage
        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kmz_images (id INTEGER PRIMARY KEY, name TEXT, data BLOB)")
        for nome_arquivo in self.zip_kmz.namelist():
            if nome_arquivo.lower().startswith('images/'):
                with self.zip_kmz.open(nome_arquivo) as imagem_file:
                    blob = imagem_file.read()
                    cur.execute("INSERT INTO kmz_images (name, data) VALUES (?, ?)", (os.path.basename(nome_arquivo), blob))
        conn.commit()
        conn.close()

        # Salva estilos na tabela Styles no GeoPackage
        styles = parse_styles(root, ns) # Extrai estilos
        # TODO: Exportar estilos em tabela no GPKG para aplicar depois
        # styles[sid] = {
        #     'id': sid,
        #     'icon_href': icon_href,
        #     'line_width': line_width,
        #     'line_opacity': line_opacity,
        #     'line_color_hex': line_color_hex,
        #     'poly_opacity': poly_opacity,
        #     'poly_color_hex': poly_color_hex
        # }

        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        # TODO: Consertar a criação da tabela de estilos
        cur.execute("CREATE TABLE IF NOT EXISTS Styles (id TEXT, icon_href TEXT, line_width INTEGER, line_opacity INTEGER, line_color_hex TEXT, poly_opacity INTEGER, poly_color_hex TEXT)")
        for style in styles:

                    cur.execute("INSERT INTO Styles (id, icon_href, line_width, line_opacity, line_color_hex, poly_opacity, poly_color_hex) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        # (styles[style]['id'], styles[style]['icon_href'], styles[style]['line_width'], styles[style]['line_opacity'], styles[style]['line_color_hex'], styles[style]['poly_opacity'], styles[style]['poly_color_hex']))
                        (style['id'], style['icon_href'], style['line_width'], style['line_opacity'], style['line_color_hex'], style['poly_opacity'], style['poly_color_hex']))
        conn.commit()
        conn.close()

        print(f"GeoPackage criado em: {gpkg_path}")
        print("Camadas por Folder e tipo criadas (inclui TrackLine e TrackPoint).")
        print("Simbologia aplicada conforme Style/styleUrl e campos de estilo gravados.")
        print("Imagens salvas na tabela 'kmz_images' e extraídas para ícones em temp.")
    
    def parse_kml(self):
        with self.zip_kmz.open('doc.kml') as kml_file:
            source_kml = kml_file.read()
            root = ET.fromstring(source_kml)
        return root
        
    def close(self):
        self.zip_kmz.close()

kmz_path = r"C:\Users\dezes\OneDrive\Documents\python\Qgis\Avenza\Avenza Ok\BSB-504-Academia.kmz" # Tem 09 Folder com pontos, linhas e polígonos
# kmz_path = r"C:\TI\Qgis\KML Testes\Avenza\3 camadas.kmz" # Tem 01 Folder com pontos, linhas e polígonos, mas sem schema e fotos
# kmz_path = r"C:\TI\Qgis\KML Testes\Avenza\MM Com Fotos Cópia.kmz" #
# kmz_path = r"C:\TI\Qgis\KML Testes\Avenza\BSB-504-Academia.kmz" # Tem 01 Folder, mas tem Track com schema e fotos, além de outros pontos e polígonos

print('\nInicializando kmz_01:')
kmz_01 = Zip_Kmz(kmz_path)
# kmz_01.salvar_em_gpkg()
print('simbologia do kmz_01:')
kmz_01.process_simbologia()
# print(f'\t{kmz_01.simbologia=}\n')
# print('schema do kmz_01:')
# kmz_01.process_schema()
# print(f'\t{kmz_01.point_cols=}\n')
# print(f'\t{kmz_01.schema=}\n')

# Listando todas as camadas do kml:
# print(f'\n\t{[x.find("kml:name", kmz_01.ns).text for x in kmz_01.root.findall(".//kml:Folder", kmz_01.ns)]=}')

# result = kmz_01.process_folders()
# kmz_01.save_images_to_gpkg()
kmz_01.close()