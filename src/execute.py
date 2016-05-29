
import util
import sys
import os
import shutil
from os import path


#execute.py region_shapefile, landuse_shapefile_folder, region_stats, landuse_mapping temp_directory output_folder
import src.algorithm_steps.aggregate_land_use_raster as aggregate_lu
import src.algorithm_steps.land_use_raster_creation as lurc
import src.algorithm_steps.calculate_region_land_use as calc_lu
import src.algorithm_steps.distribute_region_statistics as dist_stats

region_shapefile = sys.argv[1]
land_use_shapefiles = sys.argv[2]
region_stats_file = sys.argv[3]
landuse_mapping = util.load_land_use_mapping(4)
land_use_encodings = util.load_land_use_encodings(4)
temp_directory = sys.argv[5]
output_folder = sys.argv[6]

#TODO: params set somewhere else?
num_land_use_bands = len(landuse_mapping)
resolution = 100

#paths
rasterized_lu_folder = path.join(temp_directory, "land_use_rasters_10m")
merged_lu_raster = path.join(temp_directory, "merged_land_use_10m.tif")

land_use_aggregated = path.join(temp_directory, "land_use_{resolution}m.tif".format(resolution = resolution))

land_use_clipped = path.join(temp_directory, "land_use_{resolution}m_clipped.tif".format(resolution = resolution))

region_id_raster = path.join(temp_directory, "region_id_{resolution}m.tif".format(resolution = resolution))

regions_with_land_use = path.join(temp_directory, "regions_with_land_use")

pop_raster_file = path.join(output_folder, "population_{resolution}m.tif".format(resolution = resolution))
emp_raster_file = path.join(output_folder, "employment_{resolution}m.tif".format(resolution = resolution))
merged_output_file = path.join(output_folder, "pop_emp_sum_{resolution}m.tif".format(resolution = resolution))


#step flags
CLEAR_TEMP_DIR = False
ENCODE_LAND_USE_VALUES = False #we already have encoded values in the shapefile
CREATE_LAND_USE_RASTERS = False
MERGE_LAND_USE_RASTERS = False
AGGREGATE_LAND_USE_RASTERS = False
CLIP_LAND_USE_RASTERS = False
BUILD_REGION_ID_RASTER = False

CALC_REGION_LAND_USE_STATS = False
RUN_BUILD_STAT_RASTERS = False
MERGE_POP_EMP_RASTERS = True
RUN_CHECKING = True

if CLEAR_TEMP_DIR:
    #clear temp directory
    shutil.rmtree(temp_directory)
    os.mkdir(temp_directory)

if ENCODE_LAND_USE_VALUES:
    #encode land use values to new shapefile
    encoded_lu_folder = path.join(temp_directory, "encoded_landuse")
    lurc.encode_land_use_shapefiles(land_use_shapefiles, land_use_encodings, encoded_lu_folder)
    #
else:
    encoded_lu_folder = land_use_shapefiles

if CREATE_LAND_USE_RASTERS:
    #convert land use shapefile to raster
    print("\nconvert land use shapefile to raster...")
    os.mkdir(rasterized_lu_folder)
    lurc.create_land_userasters(encoded_lu_folder, rasterized_lu_folder)

if MERGE_LAND_USE_RASTERS:
    #merge land use rasters
    print("\nmerge land use rasters...")
    lurc.merge_rasters(rasterized_lu_folder, merged_lu_raster)

if AGGREGATE_LAND_USE_RASTERS:
    #aggregate land use raster
    print("\naggregate land use raster")
    aggregate_lu.run_land_use_aggregation(merged_lu_raster, num_land_use_bands, land_use_aggregated, resolution)

if CLIP_LAND_USE_RASTERS:
    #clip land use raster to region shapefile
    print "\nclip land use raster to region shapefile..."
    lurc.clip_land_use_raster(land_use_aggregated, region_shapefile, land_use_clipped)

if BUILD_REGION_ID_RASTER:
    #build region_id_raster
    print("\nbuild region_id_raster")
    lurc.create_ags_code_raster(region_shapefile, region_id_raster, resolution)

if CALC_REGION_LAND_USE_STATS:
    #calc region land_use stats
    print("\ncalc region land_use stats")
    calc_lu.calculate_region_land_use(region_shapefile, merged_lu_raster, region_stats_file, regions_with_land_use, landuse_mapping)

#build pop and employment rasters -> to output folder

if RUN_BUILD_STAT_RASTERS:
    print("\nbuild pop and employment rasters -> to output folder")
    dist_stats.distribute_region_statistics(regions_with_land_use,
                                            land_use_clipped,
                                            region_id_raster,
                                            output_folder,
                                            landuse_mapping)

#merge pop and employment rasters -> to output folder
if MERGE_POP_EMP_RASTERS:
    dist_stats.add_rasters(pop_raster_file, emp_raster_file, merged_output_file)


if RUN_CHECKING:
    dist_stats.check_raster_output(regions_with_land_use, pop_raster_file, ['pop_2008'])
    dist_stats.check_raster_output(regions_with_land_use, emp_raster_file, ['emp_2008'])
    dist_stats.check_raster_output(regions_with_land_use, merged_output_file, ['pop_2008', 'emp_2008'])





