import fiona
from fiona.crs import from_epsg, to_string
import os, subprocess

def codify_shapefile_landuse(shapefile, new_folder_path_abs, seidlung_path):
    os.mkdir(new_folder_path_abs)
    full_new_path = os.path.join(new_folder_path_abs, seidlung_path + ".shp")

    with fiona.open(shapefile, 'r') as src:
        source_driver = src.driver
        source_crs = src.crs

        new_schema = src.schema
        new_schema['properties']['objart_int'] = 'int'

        with fiona.open(full_new_path, 'w',
         driver=source_driver,
         crs=source_crs,
         schema=new_schema) as out:

            for feature in src:
                category = feature['properties']['OBJART']
                feature['properties']['objart_int'] = get_cat_code(category)
                out.write(feature)

    return full_new_path

def get_cat_code(category):
    ret = 0
    if category == 'AX_Wohnbauflaeche': ret = 1
    elif category == 'AX_FlaecheBesondererFunktionalerPraegung': ret = 2
    elif category == 'AX_FlaecheGemischterNutzung': ret = 3
    elif category == 'AX_IndustrieUndGewerbeflaeche': ret = 4
    elif category == 'AX_SportFreizeitUndErholungsflaeche': ret = 5

    return ret

def process_shapefiles(land_use_folder, new_land_use_folder):
    for ags_district in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, ags_district)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]
            ags = ags_district[0:3]

            #if int(ags) in [175, 177, 183, 187]: #only for test config

            print ags, os.path.join(folder_abs, seidlung_path)
            #for each land use shapefile, tabulate intersections for each zone in that shapefile
            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")

            new_folder_path_abs = os.path.join(new_land_use_folder, ags_district)

            codify_shapefile_landuse(full_sp_path, new_folder_path_abs, seidlung_path)


def create_rasters(land_use_folder, raster_output_folder):
    for ags_district in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, ags_district)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]
            ags = ags_district[0:3]

            #if int(ags) in [175, 177, 183, 187]: #only for test config

            print ags, os.path.join(folder_abs, seidlung_path)

            #for each land use shapefile, tabulate intersections for each zone in that shapefile
            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")
            with fiona.open(full_sp_path, 'r') as vector_f:
                (minx, miny, maxx, maxy) = map(lambda a:int(a - a % 50), vector_f.bounds)

            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]

            cmd = ["gdal_rasterize",
                              "-a_srs",
                              to_string(from_epsg(31468)),
                              "-a",
                              "objart_int",
                              "-te",
                              str(minx - 100), str(miny - 100), str(maxx+100), str(maxy+100),
                              "-tr",
                              "10.0",
                              "10.0",
                              "-ot", "Int16",
                              "-l",
                              seidlung_path,
                              full_sp_path,
                              os.path.join(raster_output_folder, ags_district + "_" + seidlung_path + '.tif')]

            print(cmd)

            subprocess.Popen(cmd)

def create_ags_code_raster(regions_shapefile, out_filename, resolution):

    with fiona.open(regions_shapefile, 'r') as vector_f:
        (minx, miny, maxx, maxy) = map(lambda a:int(a - a % 50), vector_f.bounds)

        layername = os.path.splitext(os.path.split(regions_shapefile)[-1])[0]

        cmd = ["gdal_rasterize",
                                  "-a_srs",
                                  to_string(from_epsg(31468)),
                                  "-a",
                                  "AGS_Int",
                                  "-a_nodata", "0",
                                  "-te",
                                  str(minx - 100), str(miny - 100), str(maxx+100), str(maxy+100),
                                  "-tr",
                                  str(resolution),
                                  str(resolution),
                                  "-ot", "Int32",
                                  "-l",
                                  layername,
                                  regions_shapefile,
                                  os.path.join(out_filename)]

        print(cmd)

        subprocess.Popen(cmd)

land_use_folder = "../TN_7_Landkreise_Stadt_Muenchen_TUM_Herrn"
new_land_use_folder = "../TN_7_modified"
raster_output_folder= "../TN_7_rasters2"

#os.mkdir(new_land_use_folder)
#os.mkdir(raster_output_folder)
#process_shapefiles(land_use_folder, new_land_use_folder)
create_rasters(new_land_use_folder, raster_output_folder)


#create_ags_code_raster("../../data/regional/regions/regions.shp", "../../output/regions.tif", 100)


