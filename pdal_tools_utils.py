# -*- coding: utf-8 -*-
"""
***************************************************************************
    pdal_tools_utils.py
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
import gdal
from qgis.core import (
    QgsProcessingException,
    QgsApplication
)
# modules to manage no-blocking stream reading
from threading import Thread
from queue import Queue, Empty


class PDALtoolsUtils:

    @staticmethod
    def getDriverType(filename):
        '''Get the writer or reader type basing on
        extension of filename or if it can be opne
        by gdal.'''
        if not filename:
            return None

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
                    extensions = [extension.lower() for extension in extensions]
                    if extension.lower() in extensions:
                        return 'gdal'

        if extension in ['las', 'laz']:
            return 'las'

        # I can't determine the driver to use
        # then use the default "las"
        return 'las'


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
