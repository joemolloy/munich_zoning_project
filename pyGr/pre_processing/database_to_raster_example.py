from affine import Affine
import pyGr.util as util
import rasterio
from rasterio.warp import reproject, Resampling
from fiona.crs import from_epsg
import pyproj
import numpy as np
import psycopg2
import os


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

def warp_raster_to_template(input_raster_file, template_raster_file, output_file):
    print "reprojecting raster"
    with rasterio.open(input_raster_file) as input_r:
        with rasterio.open(template_raster_file) as template_r:
            input_array = input_r.read(1)
            dest_array = np.zeros((template_r.width, template_r.height), dtype=input_array.dtype)

    reproject(
        input_array,
        dest_array,
        src_transform=input_r.affine,
        src_crs=input_r.crs,
        dst_transform=template_r.affine,
        dst_crs=template_r.crs,
        resampling=Resampling.nearest)

    print "now saving raster"

    with rasterio.open(output_file, 'w',
                  driver = "GTiff",
                  width=template_r.width,
                  height=template_r.height,
                  count=1,
                  dtype=dest_array.dtype,
                  crs=template_r.crs,
                  transform=template_r.affine,
                  nodata=0
                 ) as output:
        output.write(dest_array, indexes=1)


def calculate_study_area_offsets(region_id_file, population_crs):
    with rasterio.open(region_id_file) as r_id_f:
        clipping_affine = r_id_f.affine
        region_crs = pyproj.Proj(r_id_f.crs)
        height = r_id_f.height
        width = r_id_f.width

        xoff = clipping_affine.xoff
        yoff = clipping_affine.yoff
        print "region x,y offsets:", (xoff, yoff)
        population_crs = pyproj.Proj(population_crs)
        print population_crs
        xmin, ymax = pyproj.transform(region_crs, population_crs, xoff, yoff)

        xmax = xmin + width*100
        ymin = ymax - height*100

        print "pop offsets:", xmin, ymin, xmax, ymax
        return xmin, ymin, xmax, ymax

if __name__ == "__main__":

    Config = util.load_config("config/database_config.ini")
    region_id_file = "data/temp/region_id_100m.tif"
    pop_raster_file = "data/temp/population_zensus_raster.tiff"

    if os.path.exists(pop_raster_file):
        with rasterio.open(pop_raster_file) as r:
            pop_array = r.read(1)
            affine = r.affine
    else:
        population_crs = from_epsg(Config.getint("Input", "EPSGspatialReference"))
        (min_x, min_y, max_x, max_y) = calculate_study_area_offsets(region_id_file, population_crs)
        (pop_array, affine) = load_data2(Config, min_x, min_y, max_x, max_y)
        (height, width) = pop_array.shape

        with rasterio.open(pop_raster_file, 'w',
                      driver = "GTiff",
                      width=width,
                      height=height,
                      count=1,
                      dtype=rasterio.int32,
                      crs=population_crs,
                      transform=affine,
                      nodata=0
                     ) as output:
            output.write(pop_array, indexes=1)

    output_file = "data/temp/population_zensus_raster_trimmed.tiff"

    warp_raster_to_template(pop_raster_file, region_id_file, output_file)