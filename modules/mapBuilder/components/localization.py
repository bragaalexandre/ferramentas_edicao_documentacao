from pathlib import Path

from PyQt5.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsPalLayerSettings,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsRuleBasedLabeling,
    QgsTextBufferSettings,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsSymbolLayerRegistry,
    QgsTextFormat,
    QgsVectorLayer,
    QgsPainting,
)

from ....interfaces.iComponent import IComponent
from .componentUtils import ComponentUtils


class Localization(ComponentUtils, IComponent):
    def __init__(self, *args, **kwargs):
        self.stylesFolder = (
            Path(__file__).parent.parent / "resources" / "styles" / "localization"
        )
        self.shpFolder = Path(__file__).parent.parent / "resources" / "limits" / "2020"
        self.stateShpPath = self.shpFolder / "Estados_2020.shp"

    def build(
        self,
        composition: QgsPrintLayout,
        data: dict,
        mapAreaFeature: QgsFeature,
        showLayers: bool = False,
    ):
        mapIDsToBeDisplayed = []
        instance = QgsProject.instance()
        isInternational = bool(data.get("territorio_internacional"))

        # Creating layer for mapArea
        mapAreaBoundingBox = mapAreaFeature.geometry().boundingBox()
        mapAreaLayer = self.createGridRectangle(
            mapAreaBoundingBox, data, "localizationMapArea"
        )
        mapIDsToBeDisplayed.append(mapAreaLayer.id())

        # Getting state layer
        stateLayerBackground = self.loadShapeLayer(
            self.stateShpPath, "", "backgroundStates"
        )
        mapExtents = self.getExtent(
            mapAreaFeature, stateLayerBackground, isInternational
        )
        self.setupBackgroundLayer(stateLayerBackground)
        self.setLabel(stateLayerBackground, isInternational)
        mapIDsToBeDisplayed.append(stateLayerBackground.id())

        uriPath = self.shpFolder / "Paises_2020.shp"
        stylePath = self.stylesFolder / "paises.qml"
        layerCountryArea = self.loadShapeLayer(uriPath, stylePath, "countries")

        uriPath = self.shpFolder / "Oceano_2020.shp"
        stylePath = self.stylesFolder / "oceano.qml"
        layerOcean = self.loadShapeLayer(uriPath, stylePath, "ocean")

        stylePath = self.stylesFolder / "estados.qml"
        layerState = self.loadShapeLayer(self.stateShpPath, stylePath, "states")

        mapIDsToBeDisplayed.extend(
            [layerOcean.id(), layerCountryArea.id(), layerState.id()]
        )

        layersToShow = (stateLayerBackground, layerState, layerCountryArea, layerOcean)
        # Adding layers
        for layer in layersToShow:
            instance.addMapLayer(layer, False)

        instance.addMapLayer(mapAreaLayer, False)

        # Updating composition
        self.updateComposition(composition, layersToShow, mapAreaLayer, mapExtents)

        if showLayers:
            localizationGroupNode = QgsLayerTreeGroup("localization")
            localizationGroupNode.setItemVisibilityChecked(False)
            for layer in (
                mapAreaLayer,
                stateLayerBackground,
                layerState,
                layerCountryArea,
                layerOcean,
            ):
                localizationGroupNode.addLayer(layer)
            root = instance.layerTreeRoot()
            root.addChildNode(localizationGroupNode)

        return mapIDsToBeDisplayed

    def getExtent(
        self,
        selectedFeature: QgsFeature,
        stateLayer: QgsVectorLayer,
        isInternational: bool,
    ):
        """Gets the component extents by checking intersections between selectedFeature and
        stateLayer.
        """
        self.estados = set()
        geom = selectedFeature.geometry()
        geomBbox = geom.boundingBox()
        rectBounds = [geomBbox]
        request = QgsFeatureRequest().setFilterRect(geomBbox)
        for stateFeature in stateLayer.getFeatures(request):
            # Does not display foreign states if isInternational is false
            if not isInternational and stateFeature["SIGLA_PAIS"] != "BR":
                continue
            stateGeom = stateFeature.geometry()
            if stateGeom.isMultipart():
                for singleStateItem in stateGeom.constParts():
                    singleStateAbsGeom = singleStateItem.boundary()
                    if singleStateAbsGeom.boundingBoxIntersects(geomBbox):
                        self.estados.add(stateFeature["SIGLA_UF"])
                        rectBounds.append(singleStateAbsGeom.calculateBoundingBox())
            elif geom.intersects(stateGeom):
                self.estados.add(stateFeature["SIGLA_UF"])
                rectBounds.append(stateGeom.boundingBox())
        bound = rectBounds[0]
        if len(rectBounds) > 1:
            for stateBound in rectBounds[1:]:
                bound.combineExtentWith(stateBound)
        self.growBound(bound)
        return bound

    @staticmethod
    def growBound(bounds):
        """Grows the area ("zooms out") based on bounds area"""
        area = bounds.area()
        if area < 1:
            bounds.grow(0.1)
        elif 1 < area < 10:
            bounds.grow(0.3)
        elif 10 < area < 50:
            bounds.grow(2.0)
        else:
            bounds.grow(2.3)

    def createGridRectangle(
        self, mapBounds: QgsRectangle, data: dict, layerName: str
    ) -> QgsVectorLayer:
        """Creates the mapArea layer for this component by using mapBounds.
        Also sets its style.
        """
        productType = data.get("productType")
        mapBoundsLayer = self.createVectorLayerFromIter(
            layerName, [QgsGeometry.fromRect(mapBounds)]
        )
        if productType == "omMap":
            stylePath = self.stylesFolder / "localizationMapAreaForOmMap.qml"
        else:
            stylePath = self.stylesFolder / "localizationMapArea.qml"
        self.loadStyleToLayer(mapBoundsLayer, stylePath)
        return mapBoundsLayer

    def createStateRule(self, rootRule, label):
        """
        Creates a copy of the root rule and sets its filter expression based on the field SIGLA_UF
        """
        rule = rootRule.children()[0].clone()
        rule.setLabel(label)
        expression = " \"SIGLA_UF\" = '{}'".format(label)
        rule.setFilterExpression(expression)
        return rule

    def setupBackgroundLayer(self, stateLayer):
        """
        Sets symbol rules for background layer in localization component
        """
        symbol = QgsSymbol.defaultSymbol(stateLayer.geometryType())
        registry = QgsSymbolLayerRegistry()
        fillMeta = registry.symbolLayerMetadata("SimpleFill")
        fillSymbolLayer = fillMeta.createSymbolLayer(
            {"color": "211,211,211", "outline_width": 0.1}
        )
        # Replace the default style
        symbol.deleteSymbolLayer(0)
        symbol.appendSymbolLayer(fillSymbolLayer)

        renderer = QgsRuleBasedRenderer(symbol)
        rootRule = renderer.rootRule()
        for state in self.estados:
            # Appends the rule to the rootRule
            rule = self.createStateRule(rootRule, state)
            rootRule.appendChild(rule)
        # Delete the default rule
        rootRule.removeChildAt(0)
        # Apply the renderer to the layer
        stateLayer.setRenderer(renderer)
        stateLayer.triggerRepaint()

    def setLabel(self, stateLayer, isInternational):
        """
        Sets label rules for layer in localization component
        """
        # Getting base rule
        root = QgsRuleBasedLabeling.Rule(QgsPalLayerSettings())

        # Creating Rule
        settings = QgsPalLayerSettings()
        if isInternational:
            settings.fieldName = 'concat(upper("nome"), \' - \', upper("SIGLA_PAIS"))'
        else:
            settings.fieldName = 'upper("nome")'
        settings.placement = QgsPalLayerSettings.Horizontal
        settings.centroidInside = True
        settings.isExpression = True

        textFormat = QgsTextFormat()
        textFormat.setColor(QColor(0, 0, 0, 255))
        textFormat.setSize(6)
        textFormat.setFont(QFont("Noto Sans"))

        # buffer
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(1)
        buffer.setColor(QColor("#d3d3d3"))
        buffer.setBlendMode(
            QgsPainting.getCompositionMode(
                stateLayer.customProperty(
                    "labeling/bufferBlendMode", QgsPainting.BlendLighten
                )
            )
        )
        textFormat.setBuffer(buffer)
        settings.setFormat(textFormat)

        # Add rule to root and apply to stateLayer
        rule = QgsRuleBasedLabeling.Rule(settings)
        rule.setActive(True)
        root.appendChild(rule)
        rules = QgsRuleBasedLabeling(root)
        stateLayer.setLabeling(rules)
        stateLayer.setLabelsEnabled(True)
        stateLayer.triggerRepaint()

    def updateComposition(
        self,
        composition: QgsPrintLayout,
        layersToShow: tuple[QgsVectorLayer],
        mapAreaLayer: QgsVectorLayer,
        bounds: QgsRectangle,
    ):
        if (mapItem := composition.itemById("localization")) is not None:
            mapSize = mapItem.sizeWithUnits()
            mapItem.setFixedSize(mapSize)
            mapItem.setExtent(bounds)
            mapItem.setCrs(QgsCoordinateReferenceSystem("EPSG:4674"))
            mapItem.setLayers([mapAreaLayer, *layersToShow])
            mapItem.refresh()
