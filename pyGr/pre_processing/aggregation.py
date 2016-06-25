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
from pyGr.common.math import roundup_to_multiple_of

def disaggregate(m10_raster, ratio, bands):
    assert(isinstance(ratio, int))

    new_height = roundup_to_multiple_of(m10_raster.height, ratio) / ratio
    new_width = roundup_to_multiple_of(m10_raster.width, ratio) / ratio

    land_use_array = np.zeros((new_height, new_width, bands), dtype=np.ubyte)


    for i in xrange(0, new_height):
        (row_start, row_stop) = (i* ratio, (i+1)*ratio)
        for j in xrange(0, new_width):
            (col_start, col_stop) = (j* ratio, (j+1)*ratio)
            window = m10_raster.read(window=((row_start, row_stop), (col_start, col_stop)))
            bin_counts = np.bincount(window.ravel(), minlength=bands+1)
        #    if bin_counts[0] < 100:
        #        print (i, j), bin_counts
            land_use_array[i,j] = bin_counts[1:] #exclude zero counts

    return np.rollaxis(land_use_array, 2, 0)

def run_land_use_aggregation(input_file, bands, output_file, output_resolution):
    with rasterio.open(input_file, 'r') as land_use_raster:

        affine_fine = land_use_raster.profile['affine']
        profile = land_use_raster.profile

        ratio = int(output_resolution / affine_fine.a)

        affine_gross = affine_fine * Affine.scale(ratio)

        land_use_array = disaggregate(land_use_raster, ratio, bands)

        (num_bands, new_array_height, new_array_width) = land_use_array.shape

        profile.update(dtype=land_use_array.dtype,
                       count=num_bands,
                       transform=affine_gross,
                       nodata = 0,
                       height = new_array_height,
                       width = new_array_width)

        with rasterio.open(output_file, 'w', **profile) as out:
            print land_use_array.shape , "->", output_file
            for k in xrange(0,num_bands):
                out.write(land_use_array[k], indexes=k+1)

if __name__ == "__main__":
    output_resolution = 100
    bands = 5
    input_file = "../../data/temp/merged_land_use_10m.tif"
    output_file = "../../data/temp/land_use_100m_test.tif"

    run_land_use_aggregation(input_file, bands, output_file, output_resolution)