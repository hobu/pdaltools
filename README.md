QGIS Processing provider for PDAL PointCloud algorithms integration
===


Description
---

The intent of this provider is to offer a platform where to add interfaces to use PDAL inside the QGIS Processing Framework.

First algorithm added is the PDAL executor that is a basic wrapper to specify PCL inputs and a pipeline to execute.

Contributions are welcome to add new wrappers, generic pipelines, new features.

The base plugin was developed by:

* David Fernandez Arango (davidfernandezarango AT hotmail DOT com)
* Luigi Pirelli (luipir AT gmail DOT com)

dev for  : [CartoLab](http://cartolab.udc.es/cartoweb/)

Project  : [GeoMove](http://cartolab.udc.es/geomove/)

Premise
---
Please read [PDAL](https://pdal.io/) documentation first to understand how to create a json pipeline and how paramteres are passed via command line.

Dependencies
----
This provider depends on pdal command executable. Install it using you favourite package manager or, in case of Windows platform, selecting pdal package in the advanced installation of OSGeo4W Setup
This provider is tested with pdal 1.6 and 1.7.

Limitations
----
This provider does not use python_pdal due the fact the the package is for python2 and QGIS3 api are based on python3.