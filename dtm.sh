source enviro.sh

outputdir="rasters"
function dtm()
{
    mkdir -p $outputdir
    input="$1"
    bname=$( basename "$1" )
    name=${bname%.*}
    output="$outputdir/$bname.tif"
    echo $output

    command="$DOCKER run -v $HERE:/data $CONTAINER pdal translate -i /data/$input -o /data/$output --readers.las.spatialreference=EPSG:26915 --writers.gdal.data_type=float --writers.gdal.window_size=6.0 --writers.gdal.output_type=idw --writers.gdal.resolution=1.7"
    echo $command
    $command

}

dtm $1

