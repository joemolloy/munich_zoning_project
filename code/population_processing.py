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
regions_file = Config.get("Regions", "filename")

regions = util.load_regions(regions_file, zonesSaptialRef)
boundary = util.merge_polygons(regions)

(min_x, max_x, min_y, max_y) = map(int, boundary.GetEnvelope()) #given boundary, get envelope of polygon, as integers

max_dimension = max(max_x - min_x, max_y - min_y)
sub_array_size = util.next_power_of_2(max_dimension / resolution)
print "array will be size: ", sub_array_size

# need to include here


array_origin_x = (max_x + min_x - sub_array_size*resolution)/ 2
array_origin_y = (max_y + min_y - sub_array_size*resolution)/ 2

(pop_array, transform) = util.load_data(Config, array_origin_x, array_origin_y, sub_array_size)

if Config.getboolean("Parameters", "solve_iteratively"):
    result_octtree = util.solve_iteratively(Config, boundary, pop_array, transform, boundary)
else:
    pop_threshold =  Config.getint("Parameters", "population_threshold")
    result_octtree = octtree.build(boundary, pop_array, transform, pop_threshold)
    #result_octtree.prune(boundary)

result_octtree.splice(regions, pop_array, transform)

import rasterstats
polys = result_octtree.to_geom_wkb_list()
stats = rasterstats.zonal_stats(polys, pop_array, affine=transform, stats="sum", nodata=-1)
print stats


shapefile = Config.get("Land Use", "filename")
inSpatialReference = Config.getint("Land Use", "EPSGspatialReference")
output_file = Config.get("Output", "filename")

if Config.getboolean("Land Use", "calculate_land_use"):
    class_field = Config.get("Land Use", "class_field")

    (field_values, intersections) \
        = util.tabulate_intersection(result_octtree, zonesSaptialRef, shapefile, inSpatialReference, class_field)

    util.save(output_file, zonesSaptialRef, field_values, intersections)
else:
    print "error"
