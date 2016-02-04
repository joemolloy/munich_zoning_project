import numpy
from osgeo import ogr
from osgeo import osr
from osgeo import gdal
import os

import octtree

def run_build_octtree(array, origin, resolution, pop_threshold):

    tree = (array, origin, resolution, pop_threshold)

    #import matplotlib.pylab as plt
    #plt.imshow(zoned_array.astype(float))
    #plt.show()

    return tree






def export_to_raster(array, xmin, ymax, ncols, nrows, resolution, filename):
    geotransform=(xmin,resolution,0,ymax,0, -resolution)
    # That's (top left x, w-e pixel resolution, rotation (0 if North is up),
    #         top left y, rotation (0 if North is up), n-s pixel resolution)
    # I don't know why rotation is in twice???

    output_raster = gdal.GetDriverByName('GTiff').Create('popraster.tif',ncols, nrows, 1 ,gdal.GDT_Int32)  # Open the file
    output_raster.SetGeoTransform(geotransform)  # Specify its coordinates
    srs = osr.SpatialReference()                 # Establish its coordinate encoding
    srs.ImportFromEPSG(3035)                     # This one specifies WGS84 lat long.
                                                 # Anyone know how to specify the
                                                 # IAU2000:49900 Mars encoding?
    output_raster.SetProjection( srs.ExportToWkt() )   # Exports the coordinate system
                                                       # to the file
    output_raster.GetRasterBand(1).WriteArray(array)   # Writes my array to the raster
