import numpy
import os
import sys

from osgeo import ogr

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
        featureCount = layer.GetFeatureCount()
        print "Number of features in %s: %d" % (os.path.basename(shapefile),featureCount)

        feature = layer.GetFeature(0)
        geom = feature.GetGeometryRef().Clone()

        return geom



conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
cursor = conn.cursor()

resolution = 100

#100m x 100m grid.
cursor.execute("""SELECT
            count (distinct x_mp_100m),
            count (distinct y_mp_100m),
            count (*),
            min (y_mp_100m),
            max ( y_mp_100m),
            min ( x_mp_100m),
            max ( x_mp_100m)
        FROM public.muc_large_population;""")

(num_cols, num_rows, total, y_min,y_max,x_min,x_max) = cursor.fetchone()

print (num_rows, num_cols)
##### currently need a power of 2
### otherwise we could build up from the bottom, then we only need a number that is divisble by two.
assert((num_rows & (num_rows - 1)) == 0, "width must be a power of 2")
assert((num_cols & (num_cols - 1)) == 0, "height must be a power of 2")

pop_array = numpy.zeros((num_rows, num_cols), dtype=numpy.int)

#cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
#this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
cursor.execute("""SELECT x_mp_100m, y_mp_100m, "Einwohner"
                    FROM public.muc_large_population""")

for row in cursor:
    if row[2] > 0:
        x = (row[0] - x_min) / resolution
        y = (num_rows - 1) - (row[1] - y_min) / resolution
        pop_array[y,x] = row[2]
    #reference arrays by (row_no , col_no)
    #reference arrays by (   a_y,      a_x   )

print numpy.sum(pop_array)

box = ogr.Geometry(ogr.wkbLinearRing)

#Create bounding box for whole investigation area
box.AddPoint(x_min, y_min)
box.AddPoint(x_min, y_max)
box.AddPoint(x_max, y_max)
box.AddPoint(x_max, y_min)
box.AddPoint(x_min, y_min)
poly = ogr.Geometry(ogr.wkbPolygon)
poly.AddGeometry(box)


##
# if num zones is too large, we need a higher threshold
# keep a record of the thresholds that result in the nearest low, and nearest high
# for the next step, take the halfway number between the two

boundary = loadboundaries(r"boundary/munich_metro_area.shp")
desired_num_zones = 1000
pop_threshold = 1000

step = 1
solved = False
num_zones = 0
best_low = 0
best_high = 1000000 #TODO: how to pick this initial  upper limit number?
#TODO: flag to choose whether to include empty zones in counting, and when saving?

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

octtree.save_octtree_as_shapefile(result_octtree)

#next step, find the 'power of two' box that best captures the polygonal boundary area.
