# -*- coding: utf-8 -*-

"""
***************************************************************************
    pdal_pipeline_executor.py
    -------------------------
    begin                : August 2018
    copyright            : (C) 2018 by Luigi Pirelli
    email                : luipir at gmail dot com
    dev for              : http://cartolab.udc.es/cartoweb/
    Project              : http://cartolab.udc.es/geomove/
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Luigi Pirelli'
__date__ = 'August 2018'
__copyright__ = '(C) 2018, Luigi Pirelli'

# other common modules
import os
# cannot import pdal because most stable versions just use python-pdal for py2
# import pdal
from qgis.core import (
    QgsProcessingException,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString)
from ..pdal_tools_algorithm import PDALtoolsAlgorithm
from ..pdal_tools_utils import PDALtoolsUtils

class PdalPipelineExecutor(PDALtoolsAlgorithm):
    """
    Generic algorithm to process get 0|1|2 params input
    files as input to a configurable pipeline.
    The interface allow to set only one output file. Output
    can be a gdal/ogr managed format if managed by the pipeline.
    Pipeline filname is an input string becasue is the most flexible
    way to allow creting dinamic pipelines file names as input.
    In case it's necessary to have an interface to select a specific
    pipeline, would be better to integrate the executor in a processing
    modeler with file selection input.
    """

    INPUT_PCL_1 = 'INPUT_PCL_1'
    INPUT_PCL_2 = 'INPUT_PCL_2'
    INPUT_PIPELINE = 'INPUT_PIPELINE'
    INPUT_SKIP_IF_OUT_EXISTS = 'INPUT_SKIP_IF_OUT_EXISTS'
    OUTPUT_PCL = 'OUTPUT_PCL'

    def createInstance(self):
        return PdalPipelineExecutor()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'pdalpipelineexecutor'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('PDAL pipeline executor')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Utilities')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'utilities'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr(self.__doc__)

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                name=self.INPUT_PCL_1,
                description=self.tr('Input LAS/LAZ file'),
                behavior=QgsProcessingParameterFile.File,
                extension=None,
                defaultValue=None,
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                name=self.INPUT_PCL_2,
                description=self.tr('Input LAS/LAZ file'),
                behavior=QgsProcessingParameterFile.File,
                extension=None,
                defaultValue=None,
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                name=self.INPUT_PIPELINE,
                description=self.tr('Input pipeline'),
                defaultValue=None,
                optional=False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                name=self.INPUT_SKIP_IF_OUT_EXISTS,
                description=self.tr('Skip if output already exists'),
                defaultValue=True,
                optional=False
            )
        )

        # set outputs
        self.addParameter(
            QgsProcessingParameterFileDestination(
                name=self.OUTPUT_PCL,
                description=self.tr('Output file'),
                defaultValue=None,
                createByDefault=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # saving feedback in instance variable to avoid passing 
        # it to all methods. Take care if can have effects in case of
        # multithread execution
        self.feedback = feedback

        # need to skip processing?
        skip_if_out_exists = self.parameterAsBool(
            parameters,
            self.INPUT_SKIP_IF_OUT_EXISTS,
            context
        )

        # gets outputs
        output_pcl = self.parameterAsFileOutput(
            parameters,
            self.OUTPUT_PCL,
            context
        )

        # skip all process il parameter already exist
        if skip_if_out_exists and \
           os.path.exists(output_pcl) and \
           os.path.isfile(output_pcl):
            feedback.pushConsoleInfo("Skipped step because output file already exists: {}".format(output_pcl))
            return {self.OUTPUT_PCL: output_pcl}

        # no skip => gest all imputs
        input_pcl_1 = self.parameterAsFile(
            parameters,
            self.INPUT_PCL_1,
            context
        )

        input_pcl_2 = self.parameterAsFile(
            parameters,
            self.INPUT_PCL_2,
            context
        )

        pdal_pipeline = self.parameterAsString(
            parameters,
            self.INPUT_PIPELINE,
            context
        )
        if not pdal_pipeline:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_PIPELINE))
        # strips tiling and heading spaces and chars attached during drag&drop (linux)
        pdal_pipeline = pdal_pipeline.lstrip().rstrip()
        pdal_pipeline = pdal_pipeline.rstrip('\r\n')
        if pdal_pipeline.startswith('file://'):
            pdal_pipeline = pdal_pipeline[7:]
        if not os.path.exists(pdal_pipeline) or not os.path.isfile(pdal_pipeline):
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_PIPELINE))

        # first validate pipeline
        options = '--validate'
        commandline = self.createPdalCommand(
            options,
            pdal_pipeline,
            input_pcl_1,
            input_pcl_2,
            output_pcl)
        self.runAndWait(commandline)

        # run pipeline
        outDriver = PDALtoolsUtils.getDriverType(output_pcl)
        options = '--verbose=8'
        if outDriver == 'gdal':
            #options = '--verbose=8 --nostream'
            pass

        commandline = self.createPdalCommand(
            options,
            pdal_pipeline,
            input_pcl_1,
            input_pcl_2,
            output_pcl)
        self.runAndWait(commandline)

        # Return the results of the algorithm.
        return {self.OUTPUT_PCL: output_pcl}
