import os, sys
import fiona
import rasterio
from fiona.crs import to_string
import subprocess
from affine import Affine

#for each land use shapefile, create a raster, save to a folder
def create_land_use_rasters(land_use_folder, raster_output_folder, crs = None):
    for ags_district in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, ags_district)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            #TODO: Take first shapefile in list
            shapefile = [f for f in os.listdir(folder_abs) if f.endswith('.shp')][0]
                                 #if there is a name filter, filter shapefiles.

            #for each land use shapefile, tabulate intersections for each zone in that shapefile
            full_sp_path = os.path.join(folder_abs, shapefile)
            layer_name = os.path.splitext(shapefile)[0]
            with fiona.open(full_sp_path, 'r') as vector_f:
                assert crs or vector_f.crs, "a CRS must be specified either in in the shapefile or as an argument"
                if not crs:
                    crs = vector_f.crs

                (minx, miny, maxx, maxy) = map(lambda a:int(a - a % 50), vector_f.bounds)

                cmd = ["gdal_rasterize",
                                  "-a",
                                  "lu_code",
                                  "-a_srs",
                                  to_string(crs),
                                  "-te",
                                  str(minx - 100), str(miny - 100), str(maxx+100), str(maxy+100),
                                  "-tr",
                                  "10.0", #10m resolution
                                  "10.0",
                                  "-ot", "Int16",
                                  "-l",
                                  layer_name,
                                  full_sp_path,
                                  os.path.join(raster_output_folder, ags_district + "_" + layer_name + '.tif')]

                print(cmd)

                subprocess.check_call(cmd)

#create region_id raster
def create_ags_code_raster(regions_shapefile, out_filename, resolution):

    layername = os.path.splitext(os.path.split(regions_shapefile)[-1])[0]

    cmd = ["gdal_rasterize",
                              "-a",
                              "AGS_Int",
                              "-a_nodata", "0",
                              "-tr",
                              str(resolution),
                              str(resolution),
                              "-ot", "Int32",
                              "-l",
                              layername,
                              regions_shapefile,
                              os.path.join(out_filename)]

    print(cmd)

    subprocess.check_call(cmd)

def clip_land_use_raster(land_use_raster, region_shapefile, output_file):

    with rasterio.open(land_use_raster) as r:
        with fiona.open(region_shapefile) as clipper:

            (w, s, e, n) = clipper.bounds
            a = r.affine
            #TODO: need to transform the affine for new clipping
            (min_col, min_row) = map(int, ~a * (w, n))
            (max_col, max_row) = map(int, ~a * (e, s))
            w2, n2 = a * (min_col, min_row)
            new_affine = Affine.from_gdal(w2, 100, 0.0, n2, 0.0, -100)

            (height,width) = r.read(1, window = ((min_row, max_row), (min_col, max_col))).shape

            profile = r.profile
            profile.update({
                        'transform': new_affine,
                        'affine': new_affine,
                        'height': height,
                        'width': width
            })

            with rasterio.open(output_file, 'w', **profile) as out:

                for i in r.indexes:
                    clipped = r.read(i, window = ((min_row, max_row), (min_col, max_col)))
                    #print clipped.shape
                    out.write(clipped, indexes = i)


#merge rasters from folder into a single raster. #TODO: make it detect windows or osx automatically
def merge_rasters(raster_input_folder, output_raster):
    #cmd = [sys.executable, """C:\Python27\ArcGIS10.3\Scripts\gdal_merge.py""",
    cmd = ["""gdal_merge.py""",
                                  "-o",
                                  output_raster,
                                  "-n",
                                  "0"]
    input_files = [os.path.join(raster_input_folder, f)
                   for f in os.listdir(raster_input_folder)
                   if os.path.isfile(os.path.join(raster_input_folder, f))]

    cmd.extend(input_files)

    print(cmd)

    subprocess.check_call(cmd)

