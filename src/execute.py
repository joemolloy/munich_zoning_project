
import util
import sys
import os
import shutil
from os import path


#execute.py region_shapefile_w_pop_stats landuse_shapefile_folder  landuse_mapping temp_directory output_folder
import src.algorithm_steps.aggregate_land_use_raster as aggregate_lu
import src.algorithm_steps.land_use_raster_creation as lurc
import src.algorithm_steps.calculate_region_land_use as calc_lu
import src.algorithm_steps.distribute_region_statistics as dist_stats

region_shapefile = sys.argv[1]
land_use_shapefiles = sys.argv[2]
landuse_mapping = util.load_land_use_mapping(3)
land_use_encodings = util.load_land_use_encodings(3)
temp_directory = sys.argv[4]
output_folder = sys.argv[5]

shutil.rmtree(temp_directory)
os.mkdir(temp_directory)

#encode land use values to new shapefile
#encoded_lu_folder = path.join(temp_directory, "encoded_landuse")
#lurc.encode_land_use_shapefiles(land_use_shapefiles, land_use_encodings, encoded_lu_folder)

encoded_lu_folder = land_use_shapefiles

#convert land use shapefile to raster
print("\nconvert land use shapefile to raster...")
rasterized_lu_folder = path.join(temp_directory, "land_use_rasters_10m")
os.mkdir(rasterized_lu_folder)
lurc.create_land_userasters(encoded_lu_folder, rasterized_lu_folder)

#merge land use rasters
print("\nmerge land use rasters...")
merged_raster_filename = path.join(temp_directory, "merged_land_use_10m.tif")
lurc.merge_rasters(rasterized_lu_folder, merged_raster_filename)

#aggregate land use raster
print("\naggregate land use raster")
num_land_use_bands = len(landuse_mapping)
resolution = 100
land_use_aggregated = path.join(temp_directory, "land_use_{resolution}m.tif".format(resolution = resolution))
aggregate_lu.run_land_use_aggregation(merged_raster_filename, num_land_use_bands, land_use_aggregated, resolution)

#build region_id_raster
print("\nbuild region_id_raster")
region_id_raster = path.join(temp_directory, "region_id_{resolution}m.tif".format(resolution = resolution))
lurc.create_ags_code_raster(region_shapefile, region_id_raster, resolution)

#trim land use raster to region_id raster size

#calc region land_use stats
print("\ncalc region land_use stats")
regions_with_land_use = path.join(temp_directory, "regions_with_land_use")
calc_lu.calculate_region_land_use(region_shapefile, land_use_aggregated, None, regions_with_land_use, landuse_mapping)

#build pop and employment rasters -> to output folder
print("\nbuild pop and employment rasters -> to output folder")
population_output_file = path.join(output_folder, "population_{resolution}m.tif".format(resolution = resolution))
dist_stats.distribute_region_statistics(region_shapefile,
                                        land_use_aggregated,
                                        region_id_raster,
                                        population_output_file,
                                        landuse_mapping)

#merge pop and employment rasters -> to output folder






