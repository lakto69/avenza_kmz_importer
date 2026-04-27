import geopandas as gpd
from shapely.geometry import Point
from qgis.core import QgsProject, QgsVectorLayer

print(f'__name__: {__name__}, __file__: {__file__} ')
# TESTE

def cria_camada_pontos(campo_imagem='Photo Name'):
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
            "imagens": [p[campo_imagem] for p in dados_pontos], 
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

# if __name__ == "__main__":
#     cria_camada_pontos('imagens')