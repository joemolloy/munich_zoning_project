import sys, os
import util, octtree
import ConfigParser

Config = ConfigParser.ConfigParser(allow_no_value=True)

if len(sys.argv) == 1 or not os.path.exists(sys.argv[1]):
    raise IOError("please supply a configuration file as a program arugment")
Config.read(sys.argv[1])

#next step, find the 'power of two' box that best captures the polygonal boundary area.
resolution = Config.getint("Input", "resolution")
zonesSaptialRef = Config.getint("Input", "EPSGspatialReference")
boundary_file = Config.get("Boundary", "filename")

boundary = util.loadboundaries(boundary_file, zonesSaptialRef)
(min_x, max_x, min_y, max_y) = map(int, boundary.GetEnvelope()) #given boundary, get envelope of polygon, as integers

max_dimension = max(max_x - min_x, max_y - min_y)
sub_array_size = util.next_power_of_2(max_dimension / resolution)
print "array will be size: ", sub_array_size

# need to include here


array_origin_x = (max_x + min_x - sub_array_size*resolution)/ 2
array_origin_y = (max_y + min_y - sub_array_size*resolution)/ 2

pop_array = util.load_data(Config, array_origin_x, array_origin_y, sub_array_size)

print pop_array.dtype

import rasterio
from affine import Affine

aff = Affine(100,array_origin_x,0,100,array_origin_y,0)

profile = dict(
    driver="GTiff",
    width=sub_array_size,
    height=sub_array_size,
    count=1,
    dtype=rasterio.uint8,
    transform=aff
)
with rasterio.drivers():
    with rasterio.open('example-total.tif', 'w', **profile) as dst:
            dst.write(pop_array.astype(rasterio.uint8), 1)

output_file = Config.get("Output", "filename")


print "testing raster stats"
from rasterstats import zonal_stats
stats = zonal_stats(output_file, "example-total.tif")
stats[1].keys()
print [f['mean'] for f in stats]
