source enviro.sh

outputdir="laz"
function compress()
{
    mkdir -p $outputdir
    input="$1"
    bname=$( basename "$1" )
    name=${bname%.*}
    output="$outputdir/$bname.laz"
    echo $output

    command="$DOCKER run -v $HERE:/data $CONTAINER pdal translate -i /data/$input -o /data/$output --writers.las.forward=all"
    echo $command
    $command

}

compress $1

