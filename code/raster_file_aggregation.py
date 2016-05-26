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
import numpy as np
import rasterio
from affine import Affine

size = 2048
#max square area at 100m resolution is 100:
def disaggregate(m10_data):
    (height, width) = m10_data.shape
    new_array_height = height/10 + 1
    new_array_width = width/10 + 1
    print "old array: ", (height, width)
    print "new array: " , (new_array_height, new_array_width)

    land_use_array = np.zeros((6,new_array_height, new_array_width), dtype=np.ubyte)

    #start here for values : 76, 8892
    start_x = 0
    start_y = 0
    end_x = width
    end_y = height

    for y in xrange(start_y, end_y, 10):
        for x in xrange(start_x, end_x, 10):
            window = m10_data[y:y+10, x:x+10]
            (w_height, w_width) = window.shape
            if w_width * w_height > 0:

                bin_counts = np.bincount(window.ravel(), minlength=6)
                #if bin_counts[0] < 100: print bin_counts

                for i in xrange(0,5):
                    land_use_array[i, y/10, x/10] = bin_counts[i]

    print land_use_array[:,7:77, 889:899]

    return land_use_array

with rasterio.open("../land_use_merged.tif", 'r') as land_use_raster:

    affine_fine = land_use_raster.profile['affine']
    height = land_use_raster.profile['height']
    width = land_use_raster.profile['width']
    profile = land_use_raster.profile

    m10_data, = land_use_raster.read()

    #it = np.nditer(m10_data, flags=['multi_index'])
    #while not it.finished:
    #     if it[0] != 0:
    #        print "%d <%s>" % (it[0], it.multi_index)
    #     it.iternext()

    print affine_fine

    affine_gross = affine_fine * Affine.scale(10.0)
    print affine_gross


    #(bands, new_array_height, new_array_width) = (1, 2136, 1980)

    land_use_array = disaggregate(m10_data)
    (bands, new_array_height, new_array_width) = land_use_array.shape

    profile.update(dtype=rasterio.ubyte,
                   count=bands,
                   transform=affine_gross,
                   nodata = 0,
                   height = new_array_height,
                   width = new_array_width)

    with rasterio.open("../land_use_100m.tif", 'w', **profile) as out:
        print land_use_array.shape , "->", (out.height, out.width)
        for k in xrange(0,bands):
            out.write(land_use_array[k].astype(rasterio.uint8), indexes=k+1)


        #a = np.ones((new_array_height, new_array_width), dtype=rasterio.ubyte) * 127
        #out.write(a, indexes=1)

