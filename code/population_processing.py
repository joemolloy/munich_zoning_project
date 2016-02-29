import sys
import util, octtree
import ConfigParser

Config = ConfigParser.ConfigParser(allow_no_value=True)
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

array_origin_x = (max_x + min_x - sub_array_size*resolution)/ 2
array_origin_y = (max_y + min_y - sub_array_size*resolution)/ 2

pop_array = util.load_data(Config, array_origin_x, array_origin_y, sub_array_size)

if Config.getboolean("Parameters", "solve_iteratively"):
    result_octtree = util.solve_iteratively(Config, pop_array, (array_origin_x, array_origin_y), resolution, boundary)
else:
    population_threshold =  Config.getint("Parameters", "population_threshold")
    result_octtree = octtree.build(pop_array, (array_origin_x, array_origin_y), resolution, population_threshold)
    result_octtree.prune(boundary)

#result_octtree.trim(boundary)

shapefile = Config.get("Land Use", "filename")
inSpatialReference = Config.getint("Land Use", "EPSGspatialReference")
class_field = Config.get("Land Use", "class_field")

(field_values, intersections) \
    = util.tabulate_intersection(result_octtree, zonesSaptialRef, shapefile, inSpatialReference, class_field)

output_file = Config.get("Output", "filename")
util.save(output_file, zonesSaptialRef, field_values, intersections)
