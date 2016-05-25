# build employment/populations raster first
#   land use raster
#   region raster
#   shapefile of regions
#       attributes: employment
#                   population
#                   land use area coverages
#
# create numpy array same shape as population one
# for each 100x100m grid cell, use cell centrepoint to find related
#

# save population raster as tiff, dont take from

# create a 100 x 100m raster of land use, 5 bands with sqM coverage, 1 band of region
# build using a numpy array, and same affine base as population
import numpy
import rasterio
size = 2048
#max square area at 100m resolution is 100:

with rasterio.open("../combined_rasters.tif", 'r') as land_use_raster:
    lu, = land_use_raster.read()

    print lu.shape
    print land_use_raster.profile

    land_use_array = numpy.zeros((size, size), dtype=numpy.uint8)


