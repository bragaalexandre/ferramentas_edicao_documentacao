from qgis.core import (QgsFeatureRequest, QgsProcessing,
                       QgsProcessingAlgorithm, QgsProcessingParameterField,
                       QgsProcessingParameterVectorLayer)
from qgis.PyQt.QtCore import QCoreApplication


class HighestSpotOnTheFrame(QgsProcessingAlgorithm): 

    INPUT_SPOT_LAYER = 'INPUT_LAYER_P'
    INPUT_SPOT_FIELD = 'INPUT_SPOT_FIELD'
    INPUT_HIGHEST_SPOT_FIELD = 'INPUT_HIGHEST_SPOT_FIELD'
    INPUT_FRAME = 'INPUT_FRAME'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_SPOT_LAYER,
                self.tr('Selecionar camada de ponto cotado'),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.INPUT_SPOT_FIELD,
                self.tr('Selecionar o atributo de "cota"'), 
                type=QgsProcessingParameterField.Any, 
                parentLayerParameterName=self.INPUT_SPOT_LAYER,
                allowMultiple=False
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.INPUT_HIGHEST_SPOT_FIELD,
                self.tr('Selecionar o atributo de "cota mais alta"'), 
                type=QgsProcessingParameterField.Any, 
                parentLayerParameterName=self.INPUT_SPOT_LAYER,
                allowMultiple=False
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_FRAME,
                self.tr('Selecionar camada de moldura'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

    def processAlgorithm(self, parameters, context, feedback):      
        spotLayer = self.parameterAsVectorLayer(parameters, self.INPUT_SPOT_LAYER, context)
        spotField = self.parameterAsFields(parameters, self.INPUT_SPOT_FIELD, context)[0]
        higuestSpotField = self.parameterAsFields(parameters, self.INPUT_HIGHEST_SPOT_FIELD, context)[0]
        frameLayer = self.parameterAsVectorLayer(parameters, self.INPUT_FRAME, context)

        for frameFeature in frameLayer.getFeatures():
            frameGeometry = frameFeature.geometry()
            request = QgsFeatureRequest().setFilterRect( frameGeometry.boundingBox() ) 
            maxSpotFeature = None
            features = list( spotLayer.getFeatures( request ) )
            for spotFeature in features:
                if not( frameGeometry.intersects( spotFeature.geometry() ) ):
                    continue
                if maxSpotFeature and maxSpotFeature[ spotField ] > spotFeature[ spotField ]:
                    spotFeature[ higuestSpotField ] = 2
                    self.updateLayerFeature( spotLayer, spotFeature)
                    continue
                if maxSpotFeature:
                    maxSpotFeature[ higuestSpotField ] = 2
                    self.updateLayerFeature( spotLayer, maxSpotFeature)
                maxSpotFeature = spotFeature
                maxSpotFeature[ higuestSpotField ] = 1
                self.updateLayerFeature( spotLayer, maxSpotFeature)
                
        
        return {self.OUTPUT: ''}

    def updateLayerFeature(self, layer, feature):
        layer.startEditing()
        layer.updateFeature(feature)
   
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return HighestSpotOnTheFrame()

    def name(self):
        return 'highestspotontheframe'

    def displayName(self):
        return self.tr('Definir cota mais alta por moldura')

    def group(self):
        return self.tr('Edição')

    def groupId(self):
        return 'edicao'

    def shortHelpString(self):
        return self.tr("")
    
