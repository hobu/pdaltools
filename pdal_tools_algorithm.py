# -*- coding: utf-8 -*-
"""
***************************************************************************
    pdal_tools_algorithm.py
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

import os
import signal
import subprocess
import json

from PyQt5.QtGui import QIcon
from qgis.core import (
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingException)
from processing.tools.system import isWindows, isMac

from .pdal_tools_utils import (
    PDALtoolsUtils,
    NonBlockingStreamReader
)

class PDALtoolsAlgorithm(QgsProcessingAlgorithm):
    '''Base class for all PDAL algorithms.'''

    feedback = None
    readlineTimeout = 0.2

    def tr(self, string, context=''):
        if context == '':
            context = 'PDALtoolsAlgorithmProvider'
        return QgsApplication.translate(context, string)

    def icon(self):
        iconPath = os.path.join(os.path.dirname(__file__), 'pdal_logo_only.png')
        return QIcon(iconPath)

    def flags(self):
        return QgsProcessingAlgorithm.FlagSupportsBatch | \
               QgsProcessingAlgorithm.FlagCanCancel

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
            driver = PDALtoolsUtils.getDriverType(output_pcl)
            commandline.append("--writers.{}.filename={}".format(driver, output_pcl))

            # add BBOX if driver is gdal. BBOX is get from input_pcl_1 metadata
            # The rationale is that GDAL stage , for some version
            # is nto streamable and, due to a PDAL bug need to have
            # set BBOX as option of the writer
            if driver == 'gdal':
                if input_pcl_1:
                    pdalInfoJson = self.getPCLMetadata(input_pcl_1)
                else:
                    # get the pcl name from the pipeline
                    with open(pdal_pipeline, 'r') as f:
                        jsondata = f.readlines()
                    # strip all comments that does not part of json standard
                    jsondata = [line.strip() for line in jsondata if (not line.strip().startswith('/') and not line.strip().startswith('*') )]
                    jsondata = "".join(jsondata)
                    try:
                        jsondata = json.loads(jsondata)
                    except Exception as ex:
                        raise QgsProcessingException(str(ex))

                    stage_map = {
                        "reader1":0,
                    }
                    pcl_from_pipeline = jsondata["pipeline"][stage_map['reader1']]['filename']
                    if not pcl_from_pipeline:
                        raise QgsProcessingException("cannot determine a PCL from get boundingbox for gdal writer")

                    pdalInfoJson = self.getPCLMetadata(pcl_from_pipeline)

                minx = pdalInfoJson['metadata']['minx']
                miny = pdalInfoJson['metadata']['miny']
                maxx = pdalInfoJson['metadata']['maxx']
                maxy = pdalInfoJson['metadata']['maxy']

                # bounds format is ([minX, maxX],[minY,maxY]).
                commandline.append('--writers.{}.bounds=([{}, {}], [{}, {}])'.format(driver, minx, maxx, miny, maxy))

        return commandline

    def runAndWait(self, commandline):
        '''Subprocess pdal pipeline waiting it's end.
        Returns stdout/error log of execution. The execution is not blocking.
        '''
        executionLog = ''

        self.feedback.pushConsoleInfo(" ".join(commandline))

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
            if self.feedback.isCanceled():
                proc.kill()

            out = nbsr.readline(self.readlineTimeout)
            if out:
                self.feedback.pushConsoleInfo(out)
                executionLog += out

            # allow the dialog to be responsive allowing accept cancel process
            QgsApplication.instance().processEvents()

        # proc is terminated but could have more messages in stdout to read
        out = nbsr.readline(self.readlineTimeout)
        while out is not None:
            self.feedback.pushConsoleInfo(out)
            executionLog += out
            out = nbsr.readline(self.readlineTimeout)

        # check return code depending on platform
        if isWindows():
            pass
        else:
            # it is a unix env
            if proc.returncode == -(signal.SIGKILL.value):
                raise QgsProcessingException("Command {} has been cancelled".format(commandline))

        # check generic return code
        if proc.returncode != 0:
            raise QgsProcessingException("Failed execution of command {} with return code: {}".format(commandline, proc.returncode))

        # return only pdal log
        return executionLog
