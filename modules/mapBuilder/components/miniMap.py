from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsLayerTreeGroup,
    QgsMapLayer,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
)

from ....interfaces.iComponent import IComponent
from .componentUtils import ComponentUtils


class MiniMap(ComponentUtils, IComponent):
    def build(
        self,
        composition: QgsPrintLayout,
        mapAreaFeature: QgsFeature,
        layers: list[QgsMapLayer],
        showLayers=False,
    ):

        mapExtents = mapAreaFeature.geometry().convexHull().boundingBox()
        if not isinstance(layers, list):
            layers = [layers]
        self.updateComposition(composition, mapExtents, layers)

        if showLayers:
            miniMapGroupNode = QgsLayerTreeGroup("miniMap")
            miniMapGroupNode.setItemVisibilityChecked(False)
            for layer in layers:
                miniMapGroupNode.addLayer(layer)
            root = QgsProject.instance().layerTreeRoot()
            root.addChildNode(miniMapGroupNode)

        mapIDsToBeDisplayed = [x.id() for x in layers]

        return mapIDsToBeDisplayed

    def updateComposition(
        self,
        composition: QgsPrintLayout,
        mapExtents: QgsRectangle,
        layers: list[QgsMapLayer],
    ):
        if (mapItem := composition.itemById("miniMap")) is not None:
            mapSize = mapItem.sizeWithUnits()
            mapItem.setFixedSize(mapSize)
            if layers is not None:
                mapItem.setLayers(layers)
            mapItem.setExtent(mapExtents)
            mapItem.setCrs(QgsCoordinateReferenceSystem("EPSG:4674"))
            mapItem.refresh()
