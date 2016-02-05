import numpy
import os
from osgeo import ogr, osr
import psycopg2
import octtree


def loadboundaries(shapefile):
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # load shapefile
    dataSource = driver.Open(shapefile, 0)

    if dataSource is None:
        print 'Could not open %s' % (shapefile)
    else:
        print 'Opened %s' % (shapefile)
        layer = dataSource.GetLayer()


    # output SpatialReference


        featureCount = layer.GetFeatureCount()
        print "Number of features in %s: %d" % (os.path.basename(shapefile),featureCount)

        feature = layer.GetFeature(0)
        geom = feature.GetGeometryRef().Clone()

        #convert to EPSG:3035
        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(3035)

        geom.TransformTo(outSpatialRef)

        return geom

#Round up to next higher power of 2 (return x if it's already a power of 2).
#from http://stackoverflow.com/questions/1322510
def next_power_of_2(n):
    """
    Return next power of 2 greater than or equal to n
    """
    return 2**(n-1).bit_length()

def solve_iteratively(pop_array, (x_min, y_min), resolution, boundary):
    ##
    # if num zones is too large, we need a higher threshold
    # keep a record of the thresholds that result in the nearest low, and nearest high
    # for the next step, take the halfway number between the two

    desired_num_zones = 1000

    step = 1
    solved = False
    num_zones = 0
    best_low = 0
    best_high = 1000000 #TODO: how to pick this initial  upper limit number?
    #TODO: flag to choose whether to include empty zones in counting, and when saving?

    pop_threshold = (best_high - best_low) / 2


    while not solved: # difference greater than 10%
        result_octtree = octtree.build(pop_array, (x_min, y_min), resolution, pop_threshold)
        print 'step %d with threshold level %d' % (step, pop_threshold)
        print "\toriginal number of cells:", result_octtree.count()
        num_zones = result_octtree.prune(boundary)
        print "\tafter pruning to boundary:", num_zones
        print ''

        solved = abs(num_zones - desired_num_zones)/float(desired_num_zones) < 0.10
        if not solved:
            if num_zones > desired_num_zones:
                best_low = max (best_low, pop_threshold)
            else:
                best_high = min (best_high, pop_threshold)
            pop_threshold = (best_low + best_high) / 2

        step += 1

    print "Solution found!"
    print "\t%6d zones" % (num_zones)
    print "\t%6d threshold" % (pop_threshold)

    return result_octtree



def load_data(array_origin_x, array_origin_y, size, resolution):

    conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
    cursor = conn.cursor()


    x_max = array_origin_x + size * 100
    y_max = array_origin_y + size * 100

    #100m x 100m grid.
    # cursor.execute("""SELECT
    #             count (distinct x_mp_100m),
    #             count (distinct y_mp_100m),
    #             count (*),
    #             min (y_mp_100m),
    #             min (x_mp_100m)
    #         FROM public.muc_population""")
    #
    # (table_num_cols, table_num_rows, total, y_min,x_min) = cursor.fetchone()

    pop_array = numpy.zeros((size, size), dtype=numpy.int)

    #cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
    #this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
    print "parameters", (array_origin_x, x_max, array_origin_y, y_max)
    cursor.execute("""SELECT x_mp_100m, y_mp_100m, "Einwohner"
                        FROM public."Population"
                        WHERE x_mp_100m between %s and %s
                        AND   y_mp_100m between %s and %s
                        """, (array_origin_x, x_max, array_origin_y, y_max))

    for row in cursor:
        if row[2] > 0:
            x = (row[0] - array_origin_x) / resolution
            y = (size - 1) - (row[1] - array_origin_y) / resolution
            pop_array[y,x] = row[2]
        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print numpy.sum(pop_array)

    return pop_array

#next step, find the 'power of two' box that best captures the polygonal boundary area.
resolution = 100
boundary = loadboundaries(r"boundary/munich_metro_area.shp")
(min_x, max_x, min_y, max_y) = map(int, boundary.GetEnvelope()) #given boundary, get envelope of polygon, as integers
print "boundaries", (min_x, max_x, min_y, max_y)
#calculate max(width, height) in cells, and raise to next power2 number
max_dimension = max(max_x - min_x, max_y - min_y)
print max_dimension
sub_array_size = next_power_of_2(max_dimension / resolution)
print "array will be size: ", sub_array_size

array_origin_x = (max_x + min_x - sub_array_size*100)/ 2
array_origin_y = (max_y + min_y - sub_array_size*100)/ 2


pop_array = load_data(array_origin_x, array_origin_y, sub_array_size, resolution)

result_octtree = solve_iteratively(pop_array, (array_origin_x, array_origin_y), resolution, boundary)

octtree.save_octtree_as_shapefile(result_octtree)