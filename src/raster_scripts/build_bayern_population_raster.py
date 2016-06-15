from affine import Affine
import src.util as util
import rasterio
from rasterio.warp import reproject, Resampling
from fiona.crs import from_epsg
import pyproj
import numpy as np
import psycopg2


def load_data2(Config, min_x, min_y, max_x, max_y):
    database_string = Config.get("Input", "databaseString")
    if database_string:
        conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
    else:
        db = Config.get("Input", "database")
        user = Config.get("Input", "user")
        pw = Config.get("Input", "password")
        host = Config.get("Input", "host")

        conn = psycopg2.connect(database=db, user=user, password=pw, host=host)
    cursor = conn.cursor()

    sql = """SELECT {sql_x}, {sql_y}, {sql_value}
            FROM {sql_table}
            WHERE {sql_x} between %s and %s AND {sql_y} between %s and %s
            """.format(sql_x = Config.get("Sql", "x"),
                       sql_y = Config.get("Sql", "y"),
                       sql_value = Config.get("Sql", "value"),
                       sql_table = Config.get("Sql", "table"))

    resolution = Config.getint("Input", "resolution")

    print "parameters", (min_x, max_x, min_y, max_y)
    cursor.execute(sql, (min_x, max_x, min_y, max_y)) #xmin xmax, ymin, ymax in that order
    #ttes charhra

    records = cursor.fetchall()
    x_vals = zip(*records)[0]
    y_vals = zip(*records)[1]
    count_rows = len(set(y_vals))
    count_cols = len(set(x_vals))
    db_min_x = min(x_vals)
    db_min_y = min(y_vals)

    print (count_rows, count_cols, db_min_x, db_min_y)


    pop_array = np.zeros((count_rows, count_cols), dtype=np.int32)


    a = Affine(
            resolution,
            0,
            db_min_x, #shift from the center marking to bottom left corner
            0,
            -resolution,
            db_min_y + count_rows*resolution #shift from the center marking to bottom left corner
    )

    print "array origins: ", (db_min_x, db_min_y)


    for line in records:
        if line[2] > 0:
            (x,y) = (line[0], line[1])
            #print "(x,y): ", (x,y)
            (col, row) = ~a * (x,y)
            try:
                pop_array[row, col] = line[2]
            except IndexError:
                print "(col,row): ", (col, row), "x,y:", (x,y)

        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print np.sum(pop_array)

    return (pop_array, a)


Config = util.load_config("config/database_config.ini")

with rasterio.open("data/temp/region_id_100m.tif") as r_id_f:
    clipping_affine = r_id_f.affine
    crs = pyproj.Proj(r_id_f.crs)
    height = r_id_f.height
    width = r_id_f.width

    xoff = clipping_affine.xoff
    yoff = clipping_affine.yoff
    print "region x,y offsets:", (xoff, yoff)
    to_proj = pyproj.Proj(from_epsg(3035))
    print to_proj
    xx, yy = pyproj.transform(crs, to_proj, xoff, yoff)

    xmax = xx + width*100
    ymin = yy - height*100

    print "pop offsets:", xx, yy, xmax, ymin

(pop_array, affine) = load_data2(Config, xx, ymin, xmax, yy)
(height, width) = pop_array.shape

print (height, width)

dest = np.zeros(pop_array.shape, np.int32)

with rasterio.open("data/temp/population_zensus_raster.tiff", 'w',
              driver = "GTiff",
              width=width,
              height=height,
              count=1,
              dtype=rasterio.int32,
              crs=from_epsg(3035),
              transform=affine,
              nodata=0
             ) as output:
    output.write(pop_array, indexes=1)

print "reprojecting raster"

reproject(
    pop_array,
    dest,
    src_transform=affine,
    src_crs=from_epsg(3035),
    dst_transform=clipping_affine,
    dst_crs=r_id_f.crs,
    resampling=Resampling.nearest)

print "now saving raster"

with rasterio.open("data/temp/population_zensus_raster_trimmed.tiff", 'w',
              driver = "GTiff",
              width=width,
              height=height,
              count=1,
              dtype=rasterio.int32,
              crs=r_id_f.crs,
              transform=clipping_affine,
              nodata=0
             ) as output:
    output.write(dest, indexes=1)