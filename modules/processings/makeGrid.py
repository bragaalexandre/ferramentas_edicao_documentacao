# -*- coding: utf-8 -*-

import math

from qgis import processing
from qgis.core import (QgsCoordinateReferenceSystem, QgsFeatureSink,
                       QgsPointXY, QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingFeatureSourceDefinition,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource)
from qgis.PyQt.QtCore import QCoreApplication


class MakeGrid(QgsProcessingAlgorithm):


    INPUT_FRAME = 'INPUT_FRAME'
    INPUT_SCALE = 'INPUT_SCALE'
    OUTPUT = 'OUTPUT'
   
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_FRAME,
                self.tr('Selecione a camada de moldura'),
                types=[QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_SCALE,
                self.tr('Selecione a escala de edição:'),
                options = [self.tr('1:25.000'), self.tr('1:50.000'), self.tr('1:100.000'), self.tr('1:250.000')]
            )
        )
 
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Vetor de Grade')
            )
        ) 

    def processAlgorithm(self, parameters, context, feedback):
        inputFrameLayer = self.parameterAsSource( parameters,self.INPUT_FRAME, context )
        boolVar = self.parameterAsBool( parameters,self.INPUT_FRAME, context )
        gridScaleParam = self.parameterAsInt(parameters, self.INPUT_SCALE, context)
        frameLayer2 = self.runAddCount(inputFrameLayer, boolVar)

        if (gridScaleParam==0):
            gridScale = 25000
        elif (gridScaleParam==1):
            gridScale = 50000
        if (gridScaleParam==2):
            gridScale = 100000
        elif (gridScaleParam==3):
            gridScale = 250000

        self.runCreateSpatialIndex(frameLayer2)
        # Converter moldura para lat long
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        frameLayer = self.reprojectLayer(frameLayer2, crs)
        # Pegar centro da moldura  (se tiver mais de um polígono na camada de moldura pegar o centro dos centros)
        if frameLayer.featureCount()>1:
            xs=[]
            ys=[]
            for poly in frameLayer.getFeatures():
                centroid=QgsPointXY(poly.geometry().centroid().constGet())
                xs.append(centroid.x())
                ys.append(centroid.y())
            centroid= QgsPointXY(sum(xs)/len(xs), sum(ys)/len(ys))
        else:
            for poly in frameLayer.getFeatures():
                centroid=QgsPointXY(poly.geometry().centroid().constGet())
        # Descobrir o utm
        utmString = getSirgasAuthIdByPointLatLong(centroid.y(), centroid.x())
        utm = QgsCoordinateReferenceSystem(utmString)
        frameLayerReprojected = self.reprojectLayer(frameLayer, utm)
        # Criar a grade com 4cm (baseado na escala) de distancia entre as linhas no fuso
        gridSize = 4*gridScale/100
        ptLyrExt = frameLayerReprojected.extent()
        xmin = ptLyrExt.xMinimum()
        xmax = ptLyrExt.xMaximum()
        ymin = ptLyrExt.yMinimum()
        ymax = ptLyrExt.yMaximum()
        xmin, xmax, ymin, ymax = self.processExtent(xmin, xmax, ymin, ymax, gridSize)
        grid = self.makeGrid(gridSize, utm, xmin, xmax, ymin, ymax, parameters, context, feedback)
        # Reprojetar para CRS de destino (moldura)
        reprojectGrid = self.reprojectLayer(grid,inputFrameLayer.sourceCrs())
        lineLayer = self.convertPolygonToLines(reprojectGrid)
        newLayer = self.outLayer(parameters, context, lineLayer, 2)
        return {self.OUTPUT: newLayer}

    def runAddCount(self, inputLyr, boolVar):
        output = processing.run(
            "native:addautoincrementalfield",
            {
                'INPUT':QgsProcessingFeatureSourceDefinition(inputLyr.sourceName(), not boolVar), # boolVar recebe o contrario da checkbox de feições selecionadas
                'FIELD_NAME':'AUTO',
                'START':0,
                'GROUP_FIELDS':[],
                'SORT_EXPRESSION':'',
                'SORT_ASCENDING':False,
                'SORT_NULLS_FIRST':False,
                'OUTPUT':'TEMPORARY_OUTPUT'
            }
        )
        return output['OUTPUT']
    
    def runCreateSpatialIndex(self, inputLyr):
        processing.run(
            "native:createspatialindex",
            {'INPUT':inputLyr}
        )

        return False
    
    def convertPolygonToLines(self, inputLayer):
        output = processing.run(
            "native:polygonstolines",
            {
                'INPUT': inputLayer,
                'OUTPUT': 'memory:'
            }
        )
        return output['OUTPUT']

    def reprojectLayer(self, layer, crs):
        output = processing.run(
            "native:reprojectlayer",
            {
                'INPUT':layer,
                'TARGET_CRS':crs,
                'OUTPUT':'TEMPORARY_OUTPUT'
            }
        )
        return output['OUTPUT']


    def processExtent(self, xmin, xmax, ymin, ymax, gridSize):
        
        return ((int(xmin/gridSize))*gridSize, (int(xmax/gridSize)+1)*gridSize, (int(ymin/gridSize))*gridSize, (int(ymax/gridSize)+1)*gridSize)

    def makeGrid(self, gridSize, CRS, xmin, xmax, ymin, ymax, parameters, context, feedback):
        extent = str(str(xmin)+", "+str(xmax)+", "+str(ymin)+", "+str(ymax))
        output = processing.run(
            "native:creategrid",
            {
                'TYPE':2,
                'EXTENT': extent,
                'HSPACING':gridSize,
                'VSPACING':gridSize,
                'HOVERLAY':0,
                'VOVERLAY':0,
                'CRS':CRS,
                'OUTPUT': parameters['OUTPUT']
            }
        )
        return output['OUTPUT']
    
    def convertPolygonToLines(self, inputLayer):
        output = processing.run(
            "native:polygonstolines",
            {
                'INPUT': inputLayer,
                'OUTPUT': 'memory:'
            }
        )
        return output['OUTPUT']
    
    def outLayer(self, parameters, context, layer, type):

        (sink, newLayer) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            layer.fields(),
            type, #1point 2line 3polygon 4multipoint 5 multiline
            layer.sourceCrs()
        )
        for feature in layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
        
        return newLayer

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MakeGrid()

    def name(self):
        return 'makegrid'

    def displayName(self):
        return self.tr('Gera Vetor de Grade')

    def group(self):
        return self.tr('Preparo de Edição')

    def groupId(self):
        return 'preparo_edicao'

    def shortHelpString(self):
        return self.tr("O algoritmo gera o vetor de grade em UTM no fuso correto baseado na moldura e reprojeta para o epsg de interesse")
    
def getSirgasAuthIdByPointLatLong(lat, long):
        """
        Calculates SIRGAS 2000 epsg.
        <h2>Example usage:</h2>
        <ul>
        <li>Found: getSirgarAuthIdByPointLatLong(-8.05389, -34.881111) -> 'ESPG:31985'</li>
        <li>Not found: getSirgarAuthIdByPointLatLong(lat, long) -> ''</li>
        </ul>
        """
        zone_number = math.floor(((long + 180) / 6) % 60) + 1
        if lat >= 0:
            zone_letter = 'N'
        else:
            zone_letter = 'S'
        return getSirgasEpsg('{0}{1}'.format(zone_number, zone_letter))

def getSirgasEpsg(key):
    options = {
        "11N" : "EPSG:31965", 
        "12N" : "EPSG:31966", 
        "13N" : "EPSG:31967", 
        "14N" : "EPSG:31968", 
        "15N" : "EPSG:31969", 
        "16N" : "EPSG:31970", 
        "17N" : "EPSG:31971", 
        "18N" : "EPSG:31972", 
        "19N" : "EPSG:31973", 
        "20N" : "EPSG:31974", 
        "21N" : "EPSG:31975", 
        "22N" : "EPSG:31976", 
        "17S" : "EPSG:31977", 
        "18S" : "EPSG:31978", 
        "19S" : "EPSG:31979", 
        "20S" : "EPSG:31980", 
        "21S" : "EPSG:31981", 
        "22S" : "EPSG:31982", 
        "23S" : "EPSG:31983", 
        "24S" : "EPSG:31984", 
        "25S" : "EPSG:31985"
    }
    return options[key] if key in options else ""