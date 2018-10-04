# -*- coding: utf-8 -*-

"""
/***************************************************************************
 PDALTools
                                 A QGIS plugin
 This plugin installs PDAL Tools
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2018-10-02
        copyright            : (C) 2018 by Cartolab
        email                : luipir@gmail.com
        email                : davidfernandezarango@hotmail.com
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

__author__ = 'Cartolab'
__date__ = '2018-10-02'
__copyright__ = '(C) 2018 by Cartolab'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import os
import glob
import shutil
from PyQt5.QtGui import QIcon
from qgis.core import (
    Qgis,
    QgsProcessingProvider,
    QgsApplication,
    QgsMessageLog,
    QgsProcessingModelAlgorithm
)
from qgis.utils import iface
from processing.modeler.ModelerUtils import ModelerUtils
from processing.core.ProcessingConfig import (
    ProcessingConfig,
    Setting
)
from .algorithms.pdal_pipeline_executor import PdalPipelineExecutor


class PDALToolsProvider(QgsProcessingProvider):

    def __init__(self):
        QgsProcessingProvider.__init__(self)

        self.modelsPath = os.path.join(os.path.dirname(__file__), 'models')
        self.pipelinesPath = os.path.join(os.path.dirname(__file__), 'pipelines')
        self.messageBarTag = type(self).__name__ # e.g. string PDALToolsProvider

        # Load algorithms
        self.alglist = [PdalPipelineExecutor()]

    def load(self):
        ProcessingConfig.settingIcons[self.name()] = self.icon()
        ProcessingConfig.addSetting(Setting(self.name(), 'ACTIVATE_PDALTOOLS',
                                            self.tr('Activate'), True))
        ProcessingConfig.readSettings()
        self.refreshAlgorithms()

        if QgsApplication.processingRegistry().providerById('model'):
            self.loadModels()
        else:
            # lazy load of models waiting QGIS initialization. This would avoid
            # to load modelas when model provider is still not available in processing
            iface.initializationCompleted.connect(self.loadModels)

        return True

    def unload(self):
        ProcessingConfig.removeSetting('ACTIVATE_PDALTOOLS')

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        for alg in self.alglist:
            self.addAlgorithm( alg )

    def loadModels(self):
        '''Register models present in models folder of the plugin.'''
        modelsFiles = glob.glob(os.path.join(self.modelsPath, '*.model3'))

        for modelFileName in modelsFiles:
            alg = QgsProcessingModelAlgorithm()
            if not alg.fromFile(modelFileName):
                QgsMessageLog.logMessage(self.tr('Not well formed model: {}'.format(modelFileName)), self.messageBarTag, Qgis.Warning)
                continue

            destFilename = os.path.join(ModelerUtils.modelsFolders()[0], os.path.basename(modelFileName))
            # skip if dest exists to avoid overwrite
            if os.path.exists(destFilename):
                QgsMessageLog.logMessage(self.tr('Model already exists: {} it will be not overwritten'.format(modelFileName)), self.messageBarTag, Qgis.Warning)
                continue
            try:
                shutil.copyfile(modelFileName, destFilename)
            except Exception as ex:
                QgsMessageLog.logMessage(self.tr('Failed to install model: {} - {}'.format(modelFileName, str(ex))), self.messageBarTag, Qgis.Warning)

        QgsApplication.processingRegistry().providerById('model').refreshAlgorithms()

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'PDALtools'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.

        This string should be short (e.g. "Lastools") and localised.
        """
        return self.tr('PDALtools')

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Lastools LIDAR tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()

    def icon(self):
        iconPath = os.path.join(os.path.dirname(__file__), 'pdal_logo_only.png')
        return QIcon(iconPath)

    def svgIconPath(self):
        iconPath = os.path.join(os.path.dirname(__file__), 'pdal_logo.svg')
        return iconPath

    def tr(self, string, context=''):
        if context == '':
            context = 'PDALtoolsAlgorithmProvider'
        return QgsApplication.translate(context, string)

