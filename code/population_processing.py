
import util, octtree
import ConfigParser



#next step, find the 'power of two' box that best captures the polygonal boundary area.
resolution = 100
boundary = util.loadboundaries(r"boundary/munich_metro_area")
(min_x, max_x, min_y, max_y) = map(int, boundary.GetEnvelope()) #given boundary, get envelope of polygon, as integers

max_dimension = max(max_x - min_x, max_y - min_y)
sub_array_size = util.next_power_of_2(max_dimension / resolution)
print "array will be size: ", sub_array_size

array_origin_x = (max_x + min_x - sub_array_size*100)/ 2
array_origin_y = (max_y + min_y - sub_array_size*100)/ 2

pop_array = util.load_data(array_origin_x, array_origin_y, sub_array_size, resolution)

#result_octtree = solve_iteratively(pop_array, (array_origin_x, array_origin_y), resolution, boundary)
result_octtree = octtree.build(pop_array, (array_origin_x, array_origin_y), resolution, 4882)

#result_octtree.trim(boundary)

result_octtree.save_as_shapefile("zones")

shapefile = r"boundary/TN_Siedlung"

(field_values, intersections) = util.tabulate_intersection(result_octtree, shapefile, "OBJART")

util.save_intersections("zones", intersections, field_values)
