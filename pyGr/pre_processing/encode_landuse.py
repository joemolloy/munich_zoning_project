import fiona
from fiona.crs import to_string
import os, subprocess

#new shapefile with landuse types coverted to integer codes (needed for gdal_rasterize
def codify_shapefile_landuse(land_use_config, shapefile, new_folder_path_abs, shapefile_name):
    os.mkdir(new_folder_path_abs)
    full_new_path = os.path.join(new_folder_path_abs, shapefile_name + ".shp")
    land_use_encoding = land_use_config.encodings

    with fiona.open(shapefile, 'r') as src:
        source_driver = src.driver
        source_crs = src.crs

        new_schema = src.schema
        new_schema['properties']['lu_code'] = 'int'

        with fiona.open(full_new_path, 'w',
         driver=source_driver,
         crs=source_crs,
         schema=new_schema) as out:

            for feature in src:
                category = feature['properties'][land_use_config.class_field].lower()
                if category in land_use_encoding:
                    feature['properties']['lu_code'] = land_use_encoding[category]
                    out.write(feature)

    return full_new_path

#go through land use shapefiles, and codify each one. TODO:Generalise for non ALKIS Data
def encode_shapefiles(land_use_config, land_use_folder, new_land_use_folder):
    for ags_district in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, ags_district)
        new_shape_file_name = ags_district
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]

            print os.path.join(folder_abs, seidlung_path)
            #for each land use shapefile, tabulate intersections for each zone in that shapefile
            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")

            new_folder_path_abs = os.path.join(new_land_use_folder, ags_district)

            codify_shapefile_landuse(land_use_config, full_sp_path, new_folder_path_abs, new_shape_file_name)
