# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AvenzaKMZImporter
                                 A QGIS plugin
 This plugin import features from KML e KMZ files from Avenza Maps
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
 
 Importa arquivos KML produzidos pelo Avenza App, categorizando as feições pelo seu estilo.

                              -------------------
        begin                : 2023-05-07
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Andrés de M. Leite
        email                : leite.m.andres@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
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

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .avenza_kmz_importer_dialog import AvenzaKMZImporterDialog

class AvenzaKMZImporter:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        # locale_path = os.path.join(
        #     self.plugin_dir,
        #     'i18n',
        #     'avenza_kmz_importer_en.qm')
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'avenza_kmz_importer_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u"&Avenza Maps's KML/KMZ File Importer")

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        # Pasta dos ícones 'svg'
        self.icons_dir = os.path.join(self.plugin_dir.replace('/','\\'), 'svg')  

        # Recupera as configurações salvas
        self.settings = QSettings('MyApp', 'AvenzaKMZImporter')
        # Inicializa o diálogo e define sua posição com base nas configurações
        self.arquivo_kml = ''

        self.initDialog()
        # Recoloca a janela na posição onde foi fechada antes
        dialog_pos = self.settings.value('dialog/pos', None)
        if dialog_pos:
            self.dlg.move(dialog_pos)

        # Recuperar o tamanho da janela
        if self.settings.value('dialog/size', None) is not None:
            self.dlg.resize(self.settings.value('dialog/size', None))   

        # Define a pasta inicial do QFileDialog.getOpenFileName
        self.directory = self.settings.value('dialog/directory', self.plugin_dir)
        # Redefine self.dlg.checkBoxExpandirFeicoes.isChecked()
        self.dlg.checkBoxExpandirFeicoes.setChecked(bool(self.settings.value('dialog/expand', 'true')))
        # Redefine self.dlg.checkBoxRotularNome.isChecked()
        self.dlg.checkBoxRotularNome.setChecked(bool(self.settings.value('dialog/rotular', 'true')))

        self.t = '{http://www.opengis.net/kml/2.2}'
        self.tx = '{http://www.google.com/kml/ext/2.2}'
        self.setInicial()

    def setInicial(self):
        self.simbologia = None
        self.tree = None
        self.point_cols = ['Name', 'geometry', 'Time', 'Style', 'Notes', 'Icon_URL', 'Icon_local']
        self.esquemas = {}


    def initDialog(self):
        # Inicialize o diálogo e faça todas as configurações necessárias
        # Create an instance of your custom dialog
        self.dlg = AvenzaKMZImporterDialog()

        # Set up the dialog connections
        self.dlg.tbEscolherArquivo.clicked.connect(self.tbEscolherArquivo)
        self.dlg.pushBtImportar.clicked.connect(self.pushBtImportar)
        self.dlg.lineEdit_KML.textChanged.connect(self.idle_pushBtImportar)
        self.dlg.button_box.rejected.connect(self.dlg.close)

        # Conectar o evento de fechamento do diálogo para salvar a posição
        self.dlg.finished.connect(self.saveDialogPosition)

        # Internacionalizando o app:
        self.dlg.label.setText(self.tr('Arquivo KML ou KMZ:'))
        self.dlg.lineEdit_KML.setToolTip(self.tr('Use o botão ao lado para escolher o arquivo a ser adicionado no projeto.'))
        self.dlg.lineEdit_KML.setPlaceholderText(self.tr('Use o botão ao lado para escolher o arquivo...'))
        self.dlg.tbEscolherArquivo.setToolTip(self.tr('Clique aqui para escolher o arquivo a ser adicionado no projeto.'))
        self.dlg.tbEscolherArquivo.setText(self.tr('Escolher arquivo.'))
        self.dlg.label_2.setText(self.tr('Adicionar ao Grupo:'))
        self.dlg.lineEdit_Grupo.setToolTip(self.tr('Caso esteja em branco, as feições serão importadas para o grupo "Avenza".'))
        self.dlg.checkBoxExpandirFeicoes.setText(self.tr('Expandir Todas as Feições'))
        self.dlg.checkBoxExpandirFeicoes.setToolTip(self.tr('Marque para que o Grupo criado seja expandido.'))
        self.dlg.checkBoxRotularNome.setText(self.tr('Rotular Feições Pelos Nomes'))
        self.dlg.groupBox.setTitle(self.tr('Processamento....'))
        self.dlg.pushBtImportar.setText(self.tr('I&mportar'))
        self.dlg.setWindowTitle(self.tr('Importar Arquivo KML ou KMZ do Avenza'))

    def saveDialogPosition(self, result):
        """Este método será chamado quando o diálogo for fechado"""
        # Salvar a posição atual do diálogo
        self.settings.setValue('dialog/pos', self.dlg.pos())
        # Salvar a situação atual de expandir o grupo
        self.settings.setValue('dialog/expand', self.dlg.checkBoxExpandirFeicoes.isChecked())
        # Salvar a situação atual de rotular feições
        self.settings.setValue('dialog/rotular', self.dlg.checkBoxRotularNome.isChecked())
        # Salvar o tamanho da janela
        self.settings.setValue('dialog/size', self.dlg.size())        

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        # return QCoreApplication.translate('AvenzaKMZImporter', message) # <- Única linha original
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', 'AvenzaKMZImporter_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            translator = QTranslator()
            translator.load(locale_path)
            QCoreApplication.installTranslator(translator)
        return QCoreApplication.translate('AvenzaKMZImporter', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/avenza_kmz_importer/icon.png'
        # icon_path = ':/plugins/avenza_kmz_importer/icon.ico'
        self.add_action(
            icon_path,
            text=self.tr(u'Avenza KML/KMZ'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u"&Avenza Maps's KML/KMZ File Importer"),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        # if self.first_start == True:
        #     self.first_start = False
        #     self.dlg = AvenzaKMZImporterDialog()

        # Funções de initializeção:
        self.initialize()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            self.cursor_arrow()

    def tbEscolherArquivo(self):
        """ 
        Abre a janela de diálogo para abrir um arquivo KML
        e preenche o lineEdit_KML com esse valor
        """
        self.cursor_wait()

        filtro = self.tr(u"Arquivos KML/KMZ (*.kml *.kmz)")
        kml_abrir = str(QFileDialog.getOpenFileName(caption=self.tr(u"Escolha o arquivo KML ou KMZ..."), directory=self.directory, filter=filtro)[0])

        # Se a kml_abrir <> Vazio
        if (kml_abrir != ""):
            # Escreve no campo lineEdit_KML
            self.dlg.lineEdit_KML.setText(kml_abrir)
            self.dlg.pushBtImportar.setDisabled(False)
            self.settings.setValue('dialog/directory', os.path.dirname(kml_abrir))
            self.dlg.lineEdit_Grupo.setText(os.path.basename(kml_abrir))

        self.cursor_arrow()            

    def idle_pushBtImportar(self):
        if os.path.exists(self.dlg.lineEdit_KML.text()):
            self.dlg.pushBtImportar.setDisabled(False)
        else:
            self.dlg.pushBtImportar.setDisabled(True)

    def pushBtImportar(self):
        self.cursor_wait()
        self.dlg.textBrowser_Log.clear()
        self.setInicial()

        self.arquivo_kml = self.dlg.lineEdit_KML.text()

        if self.dlg.lineEdit_Grupo.text()=='':
            grupo = 'Avenza'
        else:
            grupo = self.dlg.lineEdit_Grupo.text()

        # Adicionando grupo
        root = QgsProject.instance().layerTreeRoot()
        self.node_group = root.addGroup(grupo)

        # Parseando o arquivo `KML`:
        # Verificando se o arquivo é KML ou KMZ
        if self.arquivo_kml.lower().endswith('.kmz'):
            source_kml, name_kml = self.extract_kml_from_kmz(self.arquivo_kml)
            # self.add_log('Processando o arquivo', name_kml)
            self.add_log('Processando o arquivo KMZ', self.arquivo_kml)
            self.add_log('Processando o arquivo KML interno', name_kml)            
            self.tree = etree.fromstring(source_kml)
        else:
            self.add_log('Processando o arquivo KML', self.arquivo_kml)
            self.tree = etree.parse(self.arquivo_kml)

        self.process_simbologia(self.tree)
        # self.add_log(self.tr(u'Simbologia'), self.simbologia)

        self.process_schema(self.tree)
        # self.add_log('Schema', self.esquemas)
        self.add_log(self.tr(u'Processando Camadas'), '-' * 30)
        self.process_folders(self.tree)
        
        if self.node_group and self.node_group.findLayers()==[]:
            root.removeChildNode(self.node_group)

        self.cursor_arrow()
           
    def add_df_to_qgis(self, df_camada, nome_camada, simbologia_camada, tipo_camada, grupo):
        """
        Recebe um DataFrame e um nome de camada.
        Adiciona esse DataFrame no Qgis numa camada com o nome nome_camada
        """
        # pass
        self.cursor_wait()
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

        self.cursor_arrow()

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

    def setExpanded(self, expandir):
        self.node_group.setExpanded(expandir)

        for i in self.node_group.findLayers():
            i.setExpanded(expandir)
            i.setCustomProperty("showFeatureCount", True)
            
        for i in self.node_group.findGroups():
            i.setExpanded(expandir)

    def extract_kml_from_kmz(self, arquivo_kmz):
        self.cursor_wait()
        try:
            with zipfile.ZipFile(arquivo_kmz, 'r') as kmz_file:
                for nome_arquivo in kmz_file.namelist():
                    if nome_arquivo.lower().endswith('.kml'):
                        with kmz_file.open(nome_arquivo) as kml_file:
                            source_kml = kml_file.read()
                            return source_kml, nome_arquivo
                        
        except Exception as e:
            self.add_log(f"{self.tr(u'Erro ao extrair KML do KMZ')} => {str(e)}\n")
        self.cursor_arrow()

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
            camada_atual = self.node_group.addGroup(camada_nome)

            self.add_log(self.tr(u'Processando Camada'), camada_nome)
            points, lines, polygons = self.process_placemarks(camada_nome, camada)
            self.add_log(self.tr(u'Feições encontradas'), f'{self.tr(u"Pontos")}:{len(points)}, {self.tr(u"Linhas")}:{len(lines)}, {self.tr(u"Polígonos")}:{len(polygons)}')

            if not (points==[] and lines==[] and polygons==[]):
                # Cria DataFrames pandas para cada tipo de feição da camada atual
                if points!=[]:
                    try:
                        df_points = pd.DataFrame(points, columns=self.point_cols)
                        self.add_df_to_qgis(df_points, 'Points', self.simbologia, 'Point', camada_atual)
                    except Exception as e:
                        self.cursor_arrow()
                        self.add_log(self.tr(u'Erro ao processar geometria'), f'{self.tr(u"Camada atual")}: {camada_atual}.<br>{self.tr(u"Colunas")}: {self.point_cols}<br>{self.tr(u"Points")}: {str(points)} <br>{self.tr(u"Erro")}: <font color="#e92121">{str(e)}</font>')
                if lines!=[]:
                    try:
                        df_lines = pd.DataFrame(lines, columns=['Name', 'geometry', 'Time', 'Style', 'Notes', 'Line Color', 'Line Width', 'Line Opacity'])    
                        self.add_df_to_qgis(df_lines, 'Lines', self.simbologia, 'LineString', camada_atual)
                    except Exception as e:
                        self.cursor_arrow()
                        self.add_log(self.tr(u'Erro ao processar geometria'), f'{self.tr(u"Camada atual")}: {camada_atual}.<br>{self.tr(u"Colunas")}: {["Name", "geometry", "Time", "Style", "Notes", "Line Color", "Line Width", "Line Opacity"]}<br>{self.tr(u"Lines")}: {str(lines)} <br>{self.tr(u"Erro")}: <font color="#e92121">{str(e)}</font>')
                if polygons!=[]:
                    try:
                        df_polygons = pd.DataFrame(polygons, columns=['Name', 'geometry', 'Time', 'Style', 'Notes', 'Line Color', 'Line Width', 'Line Opacity', 'Polygon Color', 'Polygon Opacity'])
                        self.add_df_to_qgis(df_polygons, 'Polygons', self.simbologia, 'Polygon', camada_atual)
                    except Exception as e:
                        self.cursor_arrow()
                        self.add_log(self.tr(u'Erro ao processar geometria'), f'{self.tr(u"Camada atual")}: {camada_atual}.<br>{self.tr(u"Colunas")}: {["Name", "geometry", "Time", "Style", "Notes", "Line Color", "Line Width", "Line Opacity", "Polygon Color", "Polygon Opacity"]}<br>{self.tr(u"Polygons")}: {str(polygons)} <br>{self.tr(u"Erro")}: <font color="#e92121">{str(e)}</font>')

            # Expande ou não o conteúdo do grupo
            self.setExpanded(self.dlg.checkBoxExpandirFeicoes.isChecked())
            # # Rotular feições
            # if self.dlg.checkBoxRotularNome.isChecked():
            #     self.setLabeling()

        if len(tree.xpath('//kml:Folder', namespaces={'kml': self.t[1:-1]}))==0:
            self.add_log(self.tr(u'Erro'), self.tr(u'Não foi encontrada nenhuma camada para processar.'))
    
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
                self.add_log(self.tr(u'Não foi possível importar'), f"{self.tr(u'De')}: [{camada}].<br>{self.tr(u'Feição')}: {placemark.find(f'{self.t}name').text}, {self.tr(u'por não ser do tipo')} Point, LineString, Polygon ou Track.")
                continue # Ignorar outros tipos de feição não suportados
            # Notes
            notes = {}
            for nota in placemark.findall(f'./*//{self.t}SimpleData'):
                notes[nota.attrib.values()[0]] = nota.text
            # Name
            feature_name = placemark.find(f'{self.t}name')
            if feature_name != None:
                feature_name = placemark.find(f'{self.t}name').text

            # Time
            time = placemark.find(f'./*/{self.t}when')
            if time != None:
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
                    self.add_log(self.tr(u'Erro ao processar geometria'), f'{self.tr(u"Feição")}: {feature_name}.<br>{self.tr(u"Coordenadas")}: {str(coordinates)} <br>{self.tr(u"Erro")}: <font color="#e92121">{str(e)}</font>')
            elif feature_type == 'LineString':
                try:
                    geometry = LineString(coordinates)
                    lines.append((feature_name, geometry, time, urlstyle, notes, cor_linha, espessura_linha, opacidade_linha))   
                except Exception as e:
                    self.add_log(self.tr(u'Erro ao processar geometria'), f'{self.tr(u"Feição")}: {feature_name}.<br>{self.tr(u"Coordenadas")}: {str(coordinates)} <br>{self.tr(u"Erro")}: <font color="#e92121">{str(e)}</font>')
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
    
    def sort_by_type_layer(self, node_group):
        # Classifica o grupo com base no tipo de feição, na ordem: ponto, linha e polígono
        grupo = node_group

        camadas = []
        variedade_de_feicoes = set()
        for camada in grupo.findLayers():
            camadas.append((camada.layer().geometryType(), camada.layer().id(), camada))
            variedade_de_feicoes.add(camada.layer().geometryType())

        # Caso haja mais de um tipo de feição, classifica
        if len(variedade_de_feicoes)>1:
            camadas_sorted = sorted(camadas, reverse=True)

            if camadas!=camadas_sorted:
                for camada in camadas_sorted:
                    v1 = camada[2]
                    myv1 = grupo.findLayer(v1.layer().id())
                    myvlclone = myv1.clone()
                    grupo.insertChildNode(0, myvlclone)
                    grupo.removeChildNode(myv1)
    
    def add_log(self, titulo, texto):
        # Função pra acrescentar linhas de dados ao textBrowser_Log
        # texto = '<br>' + linha + ''
        self.dlg.textBrowser_Log.insertHtml(f'<br><font color="#805080">{titulo}:</font><br>{texto}<br>')

    def initialize(self):
        self.dlg.lineEdit_KML.clear()
        self.dlg.textBrowser_Log.clear()
        self.dlg.lineEdit_Grupo.clear()
        # self.dlg.pushBtImportar.
    
    def cursor_wait(self):
        self.dlg.setCursor(Qt.CursorShape.WaitCursor)
    
    def cursor_arrow(self):
        self.dlg.setCursor(Qt.CursorShape.ArrowCursor)


