source enviro.sh

#ls laz/*.laz | parallel $DRY $RATE ./crop.sh {}
#echo "cropped/5142-11-30.laz" |  parallel $DRY $RATE ./ground.sh {}
#echo "cropped/5142-11-30.laz" |  parallel $DRY $RATE ./dtm.sh {}
ls original/*.las | parallel $DRY $RATE ./compress.sh {}
#ls cropped/*.laz | parallel $DRY $RATE ./ground.sh {}
#./raster.sh
