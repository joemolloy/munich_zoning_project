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

#(resolution of output/resolution of input) must be less than 16 + i.e. 100/10 = 10.
import numpy as np
import rasterio
from affine import Affine

#max square area at 100m resolution is 100:
def disaggregate(m10_data, ratio, bands):
    assert(isinstance(ratio, int))

    (height, width) = m10_data.shape
    new_array_height = height/ratio + 1
    new_array_width = width/ratio + 1
    print "old array: ", (height, width)
    print "new array: " , (new_array_height, new_array_width)

    if ratio < pow(2,8):
        output_data_type = rasterio.ubyte
    elif ratio < pow(2,16):
        output_data_type = rasterio.uint16
    elif ratio < pow(2,32):
        output_data_type = rasterio.uint32
    else:
        raise Exception("compression ratio is too large, please select a smaller output resolution")


    land_use_array = np.zeros((bands,new_array_height, new_array_width), dtype=output_data_type)

    #start here for values : 76, 8892
    start_x = 0
    start_y = 0
    end_x = width
    end_y = height

    for y in xrange(start_y, end_y, ratio):
        for x in xrange(start_x, end_x, ratio):
            window = m10_data[y:y+ratio, x:x+ratio]
            (w_height, w_width) = window.shape
            if w_width * w_height > 0:

                bin_counts = np.bincount(window.ravel(), minlength=bands)
                #if bin_counts[0] < 100: print bin_counts

                for i in xrange(0,bands-1):
                    land_use_array[i, y/ratio, x/ratio] = bin_counts[i]

    return land_use_array

output_resolution = 100
bands = 6
input_file = "../land_use_merged.tif"
output_file = "../land_use_100m.tif"

def run_land_use_aggregation(input_file, bands, output_file, output_resolution):
    with rasterio.open(input_file, 'r') as land_use_raster:

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
        ratio = int(output_resolution / affine_fine.a)

        affine_gross = affine_fine * Affine.scale(ratio)
        print affine_gross


        land_use_array = disaggregate(m10_data, ratio, bands)
        (num_bands, new_array_height, new_array_width) = land_use_array.shape

        profile.update(dtype=land_use_array.dtype,
                       count=num_bands,
                       transform=affine_gross,
                       nodata = 0,
                       height = new_array_height,
                       width = new_array_width)

        with rasterio.open(output_file, 'w', **profile) as out:
            print land_use_array.shape , "->", (out.height, out.width)
            for k in xrange(0,num_bands):
                out.write(land_use_array[k], indexes=k+1)


            #a = np.ones((new_array_height, new_array_width), dtype=rasterio.ubyte) * 127
            #out.write(a, indexes=1)

if __name__ == "__main__":
    output_resolution = 100
    bands = 6
    input_file = "../land_use_merged.tif"
    output_file = "../land_use_100m.tif"

    run_land_use_aggregation(input_file, bands, output_file, output_resolution)