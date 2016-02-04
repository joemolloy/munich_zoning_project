import numpy
import pprint
from PIL import Image
from osgeo import ogr
from matplotlib import pyplot as plt
from matplotlib import cm
import psycopg2

import pprint

import zoning_algorithm2 as za


conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
cursor = conn.cursor()

resolution = 100
pop_threshold = 5000

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

(octtree, zoned_array) = za.run_build_octtree(pop_array, (x_min, y_min), resolution, pop_threshold)

za.create_shapefile(octtree)
za.export_to_raster(zoned_array, x_min, y_max, num_cols, num_rows, resolution, 'popraster.tif')

#given a polygon boundary, count number of polygons that
