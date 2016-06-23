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
from skimage.util import view_as_blocks

#max square area at 100m resolution is 100:
def disaggregate(m10_data, ratio, bands):
    assert(isinstance(ratio, int))

    (height, width) = m10_data.shape
    left_padding = ratio - (width % ratio)
    bottom_padding = ratio - (height % ratio)
    m10_padded = np.pad(m10_data, ((0,bottom_padding),(0,left_padding)), mode='constant', constant_values=0)

    blocked_a = view_as_blocks(m10_padded, (ratio,ratio))

    (cols, rows) = blocked_a.shape[:2]
    land_use_array = np.zeros((cols, rows, bands), dtype=np.ubyte)

    for i in range(blocked_a.shape[0]):
        for j in range(blocked_a.shape[1]):
            bin_counts = np.bincount(blocked_a[i][j].ravel(), minlength=bands+1)
            if bin_counts[0] < 100:
                print (i, j), bin_counts
            land_use_array[i,j] = bin_counts[1:] #exclude zero counts

    return np.rollaxis(land_use_array, 2, 0)

def run_land_use_aggregation(input_file, bands, output_file, output_resolution):
    with rasterio.open(input_file, 'r') as land_use_raster:

        affine_fine = land_use_raster.profile['affine']
        profile = land_use_raster.profile

        m10_data, = land_use_raster.read()

        ratio = int(output_resolution / affine_fine.a)

        affine_gross = affine_fine * Affine.scale(ratio)

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

if __name__ == "__main__":
    output_resolution = 100
    bands = 5
    input_file = "../../data/temp/merged_land_use_10m.tif"
    output_file = "../../data/temp/land_use_100m_test.tif"

    run_land_use_aggregation(input_file, bands, output_file, output_resolution)