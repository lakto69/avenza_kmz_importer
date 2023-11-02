# Bibliotecas:
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QSettings
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog # CAIXA DE DIÁLOGO
from qgis.core import QgsProject, QgsVectorLayer, QgsSymbol, QgsSvgMarkerSymbolLayer, QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsLineSymbol, QgsFillSymbol, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling

from lxml import etree
import zipfile
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString
import os.path

class AvenzaKMZImporter:
    def __init__(self):
        self.plugin_dir = os.path.dirname(r'C:\Users\leite.aml\AppData\Roaming\QGIS\QGIS3\profiles\Leite\python\plugins\avenza_kmz_importer')

        # Pasta dos ícones 'svg'
        self.icons_dir = os.path.join(self.plugin_dir.replace('/','\\'), 'svg')  

        self.arquivo_kml = ''

        self.t = '{http://www.opengis.net/kml/2.2}'
        self.tx = '{http://www.google.com/kml/ext/2.2}'
        self.setInicial()

    def setInicial(self):
        self.simbologia = None
        self.tree = None
        self.point_cols = ['Name', 'geometry', 'Time', 'Style', 'Notes', 'Icon_URL', 'Icon_local']
        self.esquemas = {}
        self.node_group = []

    def pushBtImportar(self, arquivo):
        self.setInicial()

        self.arquivo_kml = arquivo

        grupo = 'Teste'

        # Adicionando grupo
        root = QgsProject.instance().layerTreeRoot()
        self.node_group = root.addGroup(grupo)

        # Parseando o arquivo `KML`:
        # Verificando se o arquivo é KML ou KMZ
        if self.arquivo_kml.lower().endswith('.kmz'):
            source_kml, name_kml = self.extract_kml_from_kmz(self.arquivo_kml)
            self.add_log('Processando o arquivo KMZ', self.arquivo_kml)
            self.add_log('Processando o arquivo KML interno', name_kml)            
            self.tree = etree.fromstring(source_kml)
        else:
            self.add_log('Processando o arquivo KML', self.arquivo_kml)
            self.tree = etree.parse(self.arquivo_kml)

        self.process_simbologia(self.tree)
        self.process_schema(self.tree)
        self.add_log((u'Processando Camadas'), '-' * 30)
        self.process_folders(self.tree)
        
        if self.node_group and self.node_group.findLayers()==[]:
            root.removeChildNode(self.node_group)
            
    def setExpanded(self, expandir):
        self.node_group.setExpanded(expandir)

        for i in self.node_group.findLayers():
            i.setExpanded(expandir)
            i.setCustomProperty("showFeatureCount", True)
            
        for i in self.node_group.findGroups():
            i.setExpanded(expandir)
            
    def extract_kml_from_kmz(self, arquivo_kmz):
        try:
            with zipfile.ZipFile(arquivo_kmz, 'r') as kmz_file:
                for nome_arquivo in kmz_file.namelist():
                    if nome_arquivo.lower().endswith('.kml'):
                        with kmz_file.open(nome_arquivo) as kml_file:
                            source_kml = kml_file.read()
                            return source_kml, nome_arquivo
                        
        except Exception as e:
            self.add_log(f"{(u'Erro ao extrair KML do KMZ')} => {str(e)}\n")

    def process_simbologia(self, tree):
        # Computando as Simbologias:
        self.simbologia = {}
        # for estilo in estilos:
        for estilo in tree.xpath('//kml:Style', namespaces={'kml': self.t[1:-1]}):
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

    def process_schema(self, tree=None):
        if tree is None:
            tree = self.tree
        # Computando os esquemas de Tracks:
        # for esquema in esquemas:
        for esquema in tree.xpath('//kml:Schema', namespaces={'kml': self.t[1:-1]}):
            esquema_dic = {}
            for campos in esquema.findall(f'.//{self.tx}SimpleArrayField'):
                itens = [(campos.get(i)) for i in campos.keys()]
                esquema_dic[itens[0]] = itens[1]
            for campos in esquema.findall(f'.//{self.t}SimpleField'):
                itens = [(campos.get(i)) for i in campos.keys()]
                esquema_dic[itens[0]] = itens[1]

            self.esquemas[esquema.get("name")] = esquema_dic
        # Acrescentar colunas de trilha para os df de pontos:
        if self.esquemas.get('track_schema')!=None:
            self.point_cols = self.point_cols + ['when', 'angles'] + list(self.esquemas['track_schema'].keys())

    def process_folders(self, tree):
        # Iterar pelas Camadas
        for camada in tree.xpath('//kml:Folder', namespaces={'kml': self.t[1:-1]}):
            camada_nome = camada.find('.//kml:name', namespaces={'kml': self.t[1:-1]})
            if camada_nome is not None and camada_nome.text is not None:
                camada_nome = camada_nome.text
            else:
                camada_nome = f'Feature_{len(locals()[camada_nome]) + 1}'

            # Adicionando um grupo para a Camada atual
#            camada_atual = camada_nome
            camada_atual = self.node_group.addGroup(camada_nome)

            self.add_log((u'Processando Camada'), camada_nome)
            points, lines, polygons = self.process_placemarks(camada_nome, camada)
            self.add_log((u'Feições encontradas'), f'{(u"Pontos")}:{len(points)}, {(u"Linhas")}:{len(lines)}, {(u"Polígonos")}:{len(polygons)}')

            if not (points==[] and lines==[] and polygons==[]):
                # Cria DataFrames pandas para cada tipo de feição da camada atual
                if points!=[]:
                    try:
                        df_points = pd.DataFrame(points, columns=self.point_cols)
#                        self.node_group.append((df_points, 'Points', self.simbologia, 'Point', camada_atual))
                        self.add_df_to_qgis(df_points, 'Points', self.simbologia, 'Point', camada_atual)
                    except Exception as e:
                        self.add_log((u'Erro ao processar geometria'), f'{(u"Camada atual")}: {camada_atual}.\n{(u"Colunas")}: {self.point_cols}\n{(u"Points")}: {str(points)} \n{(u"Erro")}: <font color="#e92121">{str(e)}</font>')
                if lines!=[]:
                    try:
                        df_lines = pd.DataFrame(lines, columns=['Name', 'geometry', 'Time', 'Style', 'Notes', 'Line Color', 'Line Width', 'Line Opacity'])    
#                        self.node_group.append((df_lines, 'Lines', self.simbologia, 'LineString', camada_atual))
                        self.add_df_to_qgis(df_lines, 'Lines', self.simbologia, 'LineString', camada_atual)
                    except Exception as e:
                        self.add_log((u'Erro ao processar geometria'), f'{(u"Camada atual")}: {camada_atual}.\n{(u"Colunas")}: {["Name", "geometry", "Time", "Style", "Notes", "Line Color", "Line Width", "Line Opacity"]}\n{(u"Lines")}: {str(lines)} \n{(u"Erro")}: <font color="#e92121">{str(e)}</font>')
                if polygons!=[]:
                    try:
                        df_polygons = pd.DataFrame(polygons, columns=['Name', 'geometry', 'Time', 'Style', 'Notes', 'Line Color', 'Line Width', 'Line Opacity', 'Polygon Color', 'Polygon Opacity'])
#                        self.node_group.append((df_polygons, 'Polygons', self.simbologia, 'Polygon', camada_atual))
                        self.add_df_to_qgis(df_polygons, 'Polygons', self.simbologia, 'Polygon', camada_atual)
                    except Exception as e:
                        self.add_log((u'Erro ao processar geometria'), f'{(u"Camada atual")}: {camada_atual}.\n{(u"Colunas")}: {["Name", "geometry", "Time", "Style", "Notes", "Line Color", "Line Width", "Line Opacity", "Polygon Color", "Polygon Opacity"]}\n{(u"Polygons")}: {str(polygons)} \n{(u"Erro")}: <font color="#e92121">{str(e)}</font>')

            # Expande ou não o conteúdo do grupo
            self.setExpanded(False)
            
        if len(tree.xpath('//kml:Folder', namespaces={'kml': self.t[1:-1]}))==0:
            self.add_log((u'Erro'), (u'Não foi encontrada nenhuma camada para processar.'))
    
    def process_placemarks(self, camada, tree):
        # Listas para armazenar feições por tipo
        points = []
        polygons = []
        lines = []            
        for placemark in tree.findall(f'./{self.t}Placemark'):
            # feature_type
            if placemark.find(f'{self.t}Point') is not None:
                feature_type = 'Point'
            elif placemark.find(f'{self.t}Polygon') is not None:
                feature_type = 'Polygon'
            elif placemark.find(f'{self.t}LineString') is not None:
                feature_type = 'LineString'
            elif placemark.find(f'{self.tx}Track') is not None:
                feature_type = 'Track'
            else:
                self.add_log((u'Não foi possível importar'), f"{(u'De')}: [{camada}].\n{(u'Feição')}: {placemark.find(f'{self.t}name').text}, {(u'por não ser do tipo')} Point, LineString, Polygon ou Track.")
                continue # Ignorar outros tipos de feição não suportados
            # Notes
            notes = {}
            for nota in placemark.findall(f'./*//{self.t}SimpleData'):
                notes[nota.attrib.values()[0]] = nota.text
            # Name
            feature_name = placemark.find(f'{self.t}name').text
            # Time
            time = placemark.find(f'./*/{self.t}when').text
            # Style
            urlstyle = placemark.find(f'./{self.t}styleUrl').text.replace('#', '')
            # Icon_URL
            icon_url = self.simbologia[urlstyle].get('href')
            # Icon_local
            try:
                icon_local = self.simbologia[urlstyle].get('href').split('/')[-1].split('.')[0] + '.svg'
            except:
                icon_local  = ''
            if feature_type=='Track':
                icon_local = 'dot-and-circle.svg'
            # Cor da Linha
            cor_linha = self.simbologia[urlstyle].get('cor')
            # Espessura da Linha
            espessura_linha = self.simbologia[urlstyle].get('width')
            # Opacidade da Linha
            opacidade_linha = self.simbologia[urlstyle].get('opacidade')
            # Cor de Fundo
            cor_fundo = self.simbologia[urlstyle].get('cor_bg')
            # Opacidade do Fundo
            opacidade_fundo = self.simbologia[urlstyle].get('opacidade_bg')    
            # Coordenadas
            for coordinates_elem in placemark.findall(f'./*//{self.t}coordinates'):
                coordinates = coordinates_elem.text.strip().replace('\n', ',').replace(' ', '').split(',')
                coordinates = [(float(coordinates[i]), float(coordinates[i + 1]), float(coordinates[i + 2])) for i in range(0, len(coordinates), 3)]

            # Criar uma geometria com base no tipo de feição
            # geometry
            if feature_type == 'Point':
                geometry = Point(coordinates[0][0], coordinates[0][1], coordinates[0][2])
                if self.esquemas.get('track_schema') is not None:
                    points.append(tuple([feature_name, geometry, time, urlstyle, notes, icon_url, icon_local] + [None, None] + [None for x in list(self.esquemas['track_schema'].keys())]))
                else:
                    points.append(tuple([feature_name, geometry, time, urlstyle, notes, icon_url, icon_local]))

            elif feature_type == 'Polygon':
                try:
                    geometry = Polygon(coordinates)
                    polygons.append((feature_name, geometry, time, urlstyle, notes, cor_linha, espessura_linha, opacidade_linha, cor_fundo, opacidade_fundo))
                except Exception as e:
                    self.add_log((u'Erro ao processar geometria'), f'{(u"Feição")}: {feature_name}.\n{(u"Coordenadas")}: {str(coordinates)} \n{(u"Erro")}: <font color="#e92121">{str(e)}</font>')
            elif feature_type == 'LineString':
                try:
                    geometry = LineString(coordinates)
                    lines.append((feature_name, geometry, time, urlstyle, notes, cor_linha, espessura_linha, opacidade_linha))   
                except Exception as e:
                    self.add_log((u'Erro ao processar geometria'), f'{(u"Feição")}: {feature_name}.\n{(u"Coordenadas")}: {str(coordinates)} \n{(u"Erro")}: <font color="#e92121">{str(e)}</font>')
            elif feature_type == 'Track':
                # Deve fazer 02 procedimentos: Point e LineString
                point_geometry, line_geometry, array_data = self.extract_track_data(placemark)
                # Cria a linha
                if line_geometry is not None:
                    lines.append((feature_name, line_geometry[0], time, urlstyle, notes, cor_linha, espessura_linha, opacidade_linha))   
                # cria os pontos
                # Junta os dados Placemark + geometria de pontos + array_data:
                for i, geometry_pt in enumerate(point_geometry):
                    reg = tuple([feature_name, geometry_pt, time, urlstyle, notes, icon_url, icon_local] + list(array_data.loc[i]))
                    points.append(reg)
            else:
                pass
        return points, lines, polygons

    def conferir_SchemaData(self, schemadata):
        tamanho = set()
        faltam = []
        for i in self.esquemas['track_schema']:
            if schemadata.get(i) is not None:
                tamanho.add(len(schemadata.get(i)))
                # print(f'{i}: {tamanho}')
            else:
                faltam.append(i)

        if len(faltam)>0:
            # Faltou algum campo, consertar com None!
            if len(tamanho)==1:
                # Consertar:
                for i in faltam:
                    schemadata[i] = [None for x in range(list(tamanho)[0])]
            else:
                # Tem campos com tamanhos diferentes! Abortar!!!
                pass

    def extract_track_data(self, tree):
        # when
        when = [x.text for x in tree.find(f'.//{self.tx}Track').findall(f'{self.t}when')]
        # angles
        angles = [x.text for x in tree.find(f'.//{self.tx}Track').findall(f'{self.tx}angles')]

        coord = [x.text for x in tree.find(f'.//{self.tx}Track').findall(f'{self.tx}coord')]

        pontos = [tuple(map(float, c.split(' '))) for c in coord]
        longitude = [p[0] for p in pontos]
        latitude = [p[1] for p in pontos]
        altitude = [p[2] for p in pontos]
        # geometry
        geometry_track_points = [Point(xy) for xy in zip(longitude, latitude, altitude)]
        if len(pontos)>1:
            geometry_track_lines = [LineString([(point[0], point[1]) for point in pontos])]
        else:
            geometry_track_lines = None
        
        # Converter as listas em um DataFrame
        df = pd.DataFrame({'when': when, 'angles': angles})

        schemadata = {}
        for data in tree.find(f'.//{self.tx}Track').findall(f'.//{self.tx}SimpleArrayData'):
            if self.esquemas['track_schema'][data.get('name')] in ['float']:
                schemadata[data.get('name')] = [float(valor.text) for valor in data.findall(f'{self.tx}value')]
            elif self.esquemas['track_schema'][data.get('name')] in ['integer', 'int']:
                schemadata[data.get('name')] = [int(valor.text) for valor in data.findall(f'{self.tx}value')]
            else:
                schemadata['source'] = [valor.text for valor in data.findall(f'{self.tx}value')]

        self.conferir_SchemaData(schemadata)

        # Converter o dicionário em um DataFrame
        schemadata_df = pd.DataFrame(schemadata)

        # Anexar um DataFrame ao outro
        array_data = pd.concat([df, schemadata_df], axis=1)

        return geometry_track_points, geometry_track_lines, array_data
    
    def add_df_to_qgis(self, df_camada, nome_camada, simbologia_camada, tipo_camada, grupo):
        """
        Recebe um DataFrame e um nome de camada.
        Adiciona esse DataFrame no Qgis numa camada com o nome nome_camada
        """
        # Transformar o df em gpd
        gdf_camada = gpd.GeoDataFrame(df_camada, crs='EPSG:4326')
        # converte gpd em geojson
        json_camada = gdf_camada.to_json()
        
        # Processando a simbologia da camada
        if tipo_camada=='Point':
            # Cria o dicionário de ícones
            icones = df_camada.set_index('Style')['Icon_local'].to_dict()   

            # Atualiza o dicionário de ícones com a pasta onde o arquivo está
            for i in icones:
                icones[i] = os.path.join(self.icons_dir.replace('/', '\\'), icones[i])

            layer_add = QgsVectorLayer(json_camada, nome_camada, 'ogr')

            # Defina a coluna a ser categorizada
            column_name = 'Style'

            # Crie a classe de simbologia categorizada
            renderer = QgsCategorizedSymbolRenderer(column_name, [])

            # Crie os símbolos para cada categoria
            for value, svg_path in icones.items():
                symbol = QgsSymbol.defaultSymbol(layer_add.geometryType())
                
                # Defina o símbolo como um ícone SVG
                svg_symbol_layer = QgsSvgMarkerSymbolLayer(svg_path)
                symbol.changeSymbolLayer(0, svg_symbol_layer)
                
                category = QgsRendererCategory(value, symbol, value)
                renderer.addCategory(category)

            # Atribua a simbologia à camada
            layer_add.setRenderer(renderer)

            # Mostra a contagem de elementos
            layer_add.setCustomProperty("showFeatureCount", True)

            # Atualize a exibição da camada
            layer_add.triggerRepaint()

            # Adicionar as camadas ao projeto do QGIS
            QgsProject.instance().addMapLayer(layer_add, False)
            # Adicionando as camadas em um grupo:
            grupo.addLayer(layer_add)

        elif tipo_camada=='LineString':
            layer_add = QgsVectorLayer(json_camada, nome_camada, 'ogr')

            # Defina a coluna a ser categorizada
            column_name = 'Style'

            # Crie a classe de simbologia categorizada
            renderer = QgsCategorizedSymbolRenderer(column_name, [])

            # Crie os símbolos para cada categoria
            for estilo in df_camada.Style.unique():
                symbol = QgsSymbol.defaultSymbol(layer_add.geometryType())
                symbol.setColor(QColor(simbologia_camada[estilo].get('cor')))


                # Defina a espessura da linha em pixels
                symbol.setWidth(int((simbologia_camada[estilo].get('width'))))
                                    
                category = QgsRendererCategory(estilo, symbol, estilo)
                renderer.addCategory(category)

            # Atribua a simbologia à camada
            layer_add.setRenderer(renderer)

            # Atualize a exibição da camada
            layer_add.triggerRepaint()

            # Adicionar as camadas ao projeto do QGIS
            QgsProject.instance().addMapLayer(layer_add, False)
            # Adicionando as camadas em um grupo:
            grupo.addLayer(layer_add)
          
        elif tipo_camada=='Polygon':
            layer_add = QgsVectorLayer(json_camada, nome_camada, 'ogr')

            # Defina a coluna a ser categorizada
            column_name = 'Style'

            # Crie a classe de simbologia categorizada
            renderer = QgsCategorizedSymbolRenderer(column_name, [])

            # Crie os símbolos para cada categoria
            for estilo in df_camada.Style.unique():
                # Crie um símbolo de preenchimento para o polígono
                fill_symbol = QgsFillSymbol.createSimple({'color': simbologia_camada[estilo].get('cor_bg')})
                
                fill_symbol.setOpacity(float(simbologia_camada[estilo].get('opacidade_bg')) / 100)

                # Crie um símbolo de linha para o contorno do polígono
                line_symbol = QgsLineSymbol.createSimple({'color': simbologia_camada[estilo].get('cor')})
                            
                # Defina a espessura da linha em pixels
                line_symbol.setWidth(float(simbologia_camada[estilo].get('width')))
                
                # Defina a opacidade da linha (0 a 100)
                line_symbol.setOpacity(float(simbologia_camada[estilo].get('opacidade')) / 100)
                
                category = QgsRendererCategory(estilo, fill_symbol, estilo)
                renderer.addCategory(category)

            # Atribua a simbologia à camada
            layer_add.setRenderer(renderer)

            # Atualize a exibição da camada
            layer_add.triggerRepaint()

            # Adicionar as camadas ao projeto do QGIS
            QgsProject.instance().addMapLayer(layer_add, False)

            # Adicionando as camadas em um grupo:
            grupo.addLayer(layer_add)

        # Rotular feições
        if self.dlg.checkBoxRotularNome.isChecked():
            self.setLabeling(layer_add)

    def setLabeling(self, layer):
        # Adicionando o rótulo da camada
        label = QgsPalLayerSettings()
        label.fieldName = 'Name'
        label.isExpression = False
        if layer.geometryType()==1:
            label.placement = QgsPalLayerSettings.Line
        else:
            label.placement = QgsPalLayerSettings.AroundPoint

        layer.setLabeling(QgsVectorLayerSimpleLabeling(label))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()      
        
    def add_log(self, titulo, texto):
        # Função pra acrescentar linhas de dados ao textBrowser_Log
        # texto = '\n' + linha + ''
        # self.dlg.textBrowser_Log.insertHtml(f'\n<font color="#805080">{titulo}:</font>\n{texto}\n')
        print(f'\n{titulo}:\n{texto}\n')

km = AvenzaKMZImporter()
#km.pushBtImportar(r'C:\Users\leite.aml\Downloads\TEMP\CTON-PB\Camadas exportadas 20\Camadas exportadas 20.kml')
km.pushBtImportar(r'C:\Users\leite.aml\Downloads\TEMP\CTON-PB\Camadas exportadas 23\Camadas exportadas 23.kml')