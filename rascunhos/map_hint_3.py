from qgis.core import QgsProject, QgsVectorLayer
import geopandas as gpd
from shapely.geometry import Point

def cria_camada_pontos(campo_imagem):
    print(f'criando camada {campo_imagem}')
    dados_pontos = [
        {"nome": "Ponto A", "coords": (-47.8825, -15.7942), campo_imagem: "foto2;foto1"},
        {"nome": "Ponto X", "coords": (-47.0025, -15.7942), campo_imagem: None},
        {"nome": "Ponto B", "coords": (-43.2096, -22.9035), campo_imagem: "foto2"}
    ]
    
    gdf = gpd.GeoDataFrame(
        {
            "id": [i+1 for i in range(len(dados_pontos))],
            "nome": [p["nome"] for p in dados_pontos],
            campo_imagem: [p[campo_imagem] for p in dados_pontos], 
            "geometry": [Point(*p["coords"]) for p in dados_pontos]
        },
        crs="EPSG:4326"
    )
    print(f'gdf: {gdf.shape[0]}')

    # converte gpd em geojson
    json_camada = gdf.to_json()
    layer_add = QgsVectorLayer(json_camada, 'nome_camada_2', 'ogr')

    # Adicionar as camadas ao projeto do QGIS
    QgsProject.instance().addMapLayer(layer_add, False)

    root = QgsProject.instance().layerTreeRoot()
    node_group = root.addGroup('grupo')
    # camada_atual = node_group.addGroup('camada_nome')
    # Adicionando as camadas em um grupo:
    node_group.addLayer(layer_add)
    return layer_add


def setup_map_tip(meu_layer, basepath, field_name="Photo Name", width=80):
    # "Photo Name" é o nome do campo que contém os nomes das fotos sem extensão, separados por ";"
    # 'basepath' é o caminho onde estão as imagens.
    # O Map Tip exibe as imagens em miniatura, e cada miniatura é um link para a imagem original.
    # Se o campo "Photo Name" estiver vazio ou nulo, o Map Tip exibirá "No related image".
    # O estilo CSS é aplicado para melhorar a aparência das miniaturas e da tabela.

    # Expressão QGIS que gera o HTML
    expr = f'''
    with_variable(
        'basepath',
        'file:///{basepath}/',
        with_variable(
            'raw',
            "{field_name}",
            CASE
                WHEN @raw IS NULL OR trim(@raw) = '' THEN
                    '<b>No related image</b>'
                ELSE
                    with_variable(
                        'list',
                        string_to_array(@raw, ';'),
                        '<style>
                            td {{
                            border:2px solid blue;
                            background-color:#f0f8ff;
                            text-align:center;
                            padding:3px;
                            }}
                            img {{
                            width:{width}px;
                            height:auto;
                            image-orientation: from-image;
                            }}
                        </style>
                        <table border="0" cellspacing="1" align="center"><tr>' ||
                        array_to_string(
                            array_foreach(
                                @list,
                                '<td><a href="' || @basepath || trim(@element) || '.jpg">'
                                || '<img src="' || @basepath || trim(@element) || '.jpg"></a></td>'
                            ),
                            ''
                        ) ||
                        '</tr></table>'
                    )
            END
        )
    )
    '''

    # pega a camada pelo nome
    # TODO: Se referirir à camada sem ser pelo nome
    # layer = QgsProject.instance().mapLayersByName(layer_name)[0]
    layer = meu_layer

    # grava como HTML Map Tip, avaliando a expressão entre [% ... %]
    html_template = "[% " + expr + " %]"

    layer.setMapTipTemplate(html_template)
    layer.triggerRepaint()

    print(f"HTML Map Tip configurado para a camada: {layer.name()}")

nome_imagem = 'campo_imagens'
minha_camada = cria_camada_pontos(nome_imagem)

setup_map_tip(
    meu_layer=minha_camada, 
    field_name=nome_imagem, 
    basepath=r"C:/Users/dezes/OneDrive/Documents/python/Qgis/scripts/imagens"
    )