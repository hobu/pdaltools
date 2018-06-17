#!/bin/bash

CONTAINER="pdal/pdal:1.7"
DOCKER="docker"

DRY="--dryrun"
RATE="-j4"

HERE=`pwd`

export GDAL_DRIVER_PATH=/usr/local/lib/gdalplugins
CONTAINERRUN="docker run -it -d --entrypoint /bin/sh -v $HERE:/data $CONTAINER"


