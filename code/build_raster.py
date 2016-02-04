import numpy
from osgeo import osr
from osgeo import gdal
from matplotlib import pyplot as plt
from matplotlib import cm
import psycopg2

import pprint

import zoning_algorithm2 as za


conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
cursor = conn.cursor()


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
assert((num_rows & (num_rows - 1)) == 0)
assert((num_cols & (num_cols - 1)) == 0)
assert(num_rows % 2 == 0)

pop_array = numpy.zeros((num_rows, num_cols), dtype=numpy.int)

#cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
#this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
cursor.execute("""SELECT x_mp_100m, y_mp_100m, "Einwohner"
                    FROM public.muc_large_population
                    ORDER BY y_mp_100m DESC, x_mp_100m ASC;""")


count=0
for row in cursor:
    if row[2] > 0:
        x = (row[0] - 4350050) / 100
        y = (num_rows - 1) - (row[1] - 2740050) / 100

    #print (count/num_cols, count%num_cols)
        pop_array[y,x] = row[2]

    #reference arrays by (row_no , col_no)
    #reference arrays by (   a_y,      a_x   )

print numpy.sum(pop_array)

#plt.imshow(pop_array.astype(float))

#plt.show()

geotransform=(x_min,100,0,y_max,0, -100)
# That's (top left x, w-e pixel resolution, rotation (0 if North is up),
#         top left y, rotation (0 if North is up), n-s pixel resolution)
# I don't know why rotation is in twice???

output_raster = gdal.GetDriverByName('GTiff').Create('org_popraster.tif',num_cols, num_rows, 1 ,gdal.GDT_Int32)  # Open the file
output_raster.SetGeoTransform(geotransform)  # Specify its coordinates
srs = osr.SpatialReference()                 # Establish its coordinate encoding
srs.ImportFromEPSG(3035)                     # This one specifies WGS84 lat long.
                                         # Anyone know how to specify the
                                         # IAU2000:49900 Mars encoding?
output_raster.SetProjection( srs.ExportToWkt() )   # Exports the coordinate system
                                               # to the file
output_raster.GetRasterBand(1).WriteArray(pop_array)   # Writes my array to the raster

