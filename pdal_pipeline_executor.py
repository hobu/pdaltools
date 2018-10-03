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


# modules to manage no-blocking stream reading
from threading import Thread
from queue import Queue, Empty
# other common modules
import os
import sys
import signal
import select
import subprocess
import gdal
import json
# cannot import pdal because most stable versions just use python-pdal for py2
# import pdal
from PyQt5.QtGui import QIcon
from qgis.core import (QgsProcessing,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterString,
                       QgsApplication)
from processing.tools.system import isWindows, isMac

class PdalPipelineExecutor(QgsProcessingAlgorithm):
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

    def tr(self, string, context=''):
        if context == '':
            context = 'PDALtoolsAlgorithmProvider'
        return QgsApplication.translate(context, string)

    def createInstance(self):
        return PdalPipelineExecutor()

    def icon(self):
        iconPath = os.path.join(os.path.dirname(__file__), 'pdal_logo_only.png')
        return QIcon(iconPath)

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

    def flags(self):
        return QgsProcessingAlgorithm.FlagSupportsBatch | \
               QgsProcessingAlgorithm.FlagCanCancel

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
        # it to all methods. Take caree if can have effects in case of
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
        self.runAndWait(commandline, self.feedback)

        # run pipeline
        outDriver = self.getDriverType(output_pcl)
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
        self.runAndWait(commandline, self.feedback)

        # Return the results of the algorithm.
        return {self.OUTPUT_PCL: output_pcl}

    def createPdalCommand(self, options, pdal_pipeline, input_pcl_1, input_pcl_2, output_pcl):
        # check out driver
        commandline = ["pdal", "pipeline", options, "-i", pdal_pipeline]

        if input_pcl_1 and input_pcl_2:
            commandline.append("--stage.input1.filename={}".format(input_pcl_1))
            commandline.append("--stage.input2.filename={}".format(input_pcl_2))
        elif input_pcl_1 and not input_pcl_2:
            commandline.append("--readers.las.filename={}".format(input_pcl_1))
        elif not input_pcl_1 and not input_pcl_2:
            # not PCL inputs specified => can be set inside the pipeline
            pass
        else:
            raise QgsProcessingException("None PCL or at least {} have to be set ".format(self.INPUT_PCL_1))

        if output_pcl:
            driver = self.getDriverType(output_pcl)
            commandline.append("--writers.{}.filename={}".format(driver, output_pcl))

            # add BBOX if driver is gdal. BBOX is get from input_pcl_1 metadata
            # The rationale is that GDAL stage , for some version
            # is nto streamable and, due to a PDAL bug need to have
            # set BBOX as option of the writer
            if driver == 'gdal':
                pdalInfoJson = self.getPCLMetadata(input_pcl_1)

                minx = pdalInfoJson['metadata']['minx']
                miny = pdalInfoJson['metadata']['miny']
                maxx = pdalInfoJson['metadata']['maxx']
                maxy = pdalInfoJson['metadata']['maxy']

                # bounds format is ([minX, maxX],[minY,maxY]).
                commandline.append('--writers.{}.bounds=([{}, {}], [{}, {}])'.format(driver, minx, maxx, miny, maxy))

        return commandline

    def getDriverType(self, filename):
        '''Get the writer or reader type basing on
        extension of filename or if it can be opne
        by gdal.'''
        if os.path.exists(filename):
            dataset = gdal.Open(filename, gdal.GA_ReadOnly)
            if dataset is not None:
                # clsoe dataset
                dataset = None
                return 'gdal'

        # try to get driver by extension
        extension = os.path.splitext(filename)[1]
        if not extension:
            raise QgsProcessingException("Cannot state file type by extension for {}".format(filename))
        extension = extension[1:]

        # check if managed by gdal
        for i in range(gdal.GetDriverCount()):
            drv = gdal.GetDriver(i)
            if drv.GetMetadataItem(gdal.DCAP_RASTER):
                extensions = drv.GetMetadataItem(gdal.DMD_EXTENSIONS)
                if extensions:
                    extensions = extensions.split()
                    if extension in extensions:
                        return 'gdal'

        if extension in ['las', 'laz']:
            return 'las'

        # I can't determine the driver to use
        # then use the default "las"
        return 'las'

    def getPCLMetadata(self, pclFileName):
        '''Extract metadata with pdal info --metadata.
        Returns metadata JSON or None.'''
        metadata = None
        if pclFileName:
            options = '--metadata'
            commandline = ["pdal", "info", options, pclFileName]
            returnedJson = self.runAndWait(commandline, self.feedback)

            # clean returned string to be real json
            # e.g. skip first stdout warning: 'Warning 1: Cannot find pcs.csv'
            rows = returnedJson.split('\n')
            if 'Warning 1: Cannot find pcs.csv' in rows[0]:
                rows = rows[1:]
            returnedJson = '\n'.join(rows)

            # parse json
            try:
                metadata = json.loads(returnedJson)
            except Exception as ex:
                self.feedback.pushConsoleInfo(str(ex))

        return metadata

    def runAndWait(self, commandline, feedback):
        '''Subprocess pdal pipeline waiting it's end.
        Returns stdout/error log of execution. The execution is not blocking.
        '''
        readlineTimeout = 0.2
        executionLog = ''

        feedback.pushConsoleInfo(" ".join(commandline))

        # !Note! subprocess call is similar as in Grass7Utils.executeGrass
        # For MS-Windows, we need to hide the console window.
        if isWindows():
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.Popen(commandline,
                                shell=True if isMac() else False,
                                stdout=subprocess.PIPE,
                                stdin=open(os.devnull),
                                stderr=subprocess.STDOUT,
                                universal_newlines=True,
                                startupinfo=si if isWindows() else None)
        nbsr = NonBlockingStreamReader(proc.stdout)
        while proc.poll() is None:
            if feedback.isCanceled():
                proc.kill()

            out = nbsr.readline(readlineTimeout)
            if out:
                feedback.pushConsoleInfo(out)
                executionLog += out

            # allow the dialog to be responsive allowing accept cancel process
            QgsApplication.instance().processEvents()

        # proc is terminated but could have more messages in stdout to read
        out = nbsr.readline(readlineTimeout)
        while out is not None:
            feedback.pushConsoleInfo(out)
            executionLog += out
            out = nbsr.readline(readlineTimeout)

        # check return code depending on platform
        if sys.platform == "linux" or sys.platform == "linux2":
            if proc.returncode == -(signal.SIGKILL.value):
                raise QgsProcessingException("Command {} has been cancelled".format(commandline))
        elif sys.platform == "darwin":
            # OS X.
            pass
        elif sys.platform == "win32":
            # Windows...
            pass

        # check generic return code
        if proc.returncode != 0:
            raise QgsProcessingException("Failed execution of command {} with return code: {}".format(commandline, proc.returncode))

        # return only pdal log
        return executionLog


# snipped from:
# http://eyalarubas.com/python-subproc-nonblock.html
# tnx to: https://github.com/EyalAr
class NonBlockingStreamReader:
    '''Queue reader to avoid stdout/stderr reading block
    snipped from:
    http://eyalarubas.com/python-subproc-nonblock.html
    tnx to: https://github.com/EyalAr
    '''
    def __init__(self, stream):
        '''
        stream: the stream to read from.
                Usually a process' stdout or stderr.
        '''

        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue):
            '''
            Collect lines from 'stream' and put them in 'quque'.
            '''

            while True:
                line = stream.readline()
                if line:
                    queue.put(line)
                else:
                    raise UnexpectedEndOfStream

        self._t = Thread(target=_populateQueue,
                         args=(self._s, self._q))
        self._t.daemon = True
        self._t.start() #start collecting lines from the stream

    def readline(self, timeout=None):
        try:
            return self._q.get(block=timeout is not None,
                               timeout=timeout)
        except Empty:
            return None

class UnexpectedEndOfStream(Exception):
    pass
