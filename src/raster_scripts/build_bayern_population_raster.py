import sys, os
import src.util as util
import rasterio
import ConfigParser
from fiona.crs import from_epsg

Config = util.load_program_config()

#next step, find the 'power of two' box that best captures the polygonal boundary area.
resolution = Config.getint("Input", "resolution")
zonesSaptialRef = from_epsg(Config.getint("Input", "EPSGspatialReference"))
regions_file = Config.get("Regions", "filename")

regions = util.load_regions(regions_file, zonesSaptialRef)
boundary = util.get_region_boundary(regions)

(min_x, min_y, max_x, max_y) = map(int, boundary.bounds) #given boundary, get envelope of polygon, as integers
print (min_x, min_y, max_x, max_y)


max_dimension = max(max_x - min_x, max_y - min_y)
sub_array_size = util.next_power_of_2(max_dimension / resolution)
print "array will be size: ", sub_array_size

# need to include here


array_origin_x = (max_x + min_x - sub_array_size*resolution)/ 2
array_origin_y = (max_y + min_y - sub_array_size*resolution)/ 2

(pop_array, affine) = util.load_data(Config, array_origin_x, array_origin_y, sub_array_size)

print pop_array.shape
print "now saving raster"

with rasterio.open("../population_raster.tiff", 'w',
              driver = "GTiff",
              width=pop_array.size,
              height=pop_array.size,
              count=1,
              dtype=rasterio.int16,
              crs=zonesSaptialRef,
              transform=affine,
              nodata=0
             ) as output:
    output.write(pop_array)