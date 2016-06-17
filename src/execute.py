
import util
import os
import shutil
from os import path

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("region", help="ESRI shapefile of study area and municipalities")
parser.add_argument("population", help="Raster of zensus population. Used to distribute municipal statistics. Must be trimmed to scaled to region boundary")
parser.add_argument("land_use", help="Configuration file for land use processing, Land use data is used to disaggregate Employment data. resolution must be same as population raster")
parser.add_argument("statistics", help="Population and employment stats for each municipality")
parser.add_argument("out", help="Output_directory", default='output')

parser.add_argument("-t","--temp", help="Temporary directory", default='temp')
parser.add_argument("-s", "--start", help="algorithm step to start from.\nAll file required from this point must be in the temp or output folder")
parser.add_argument("-c", "--check", help="output statistical error information on completion", action="store_true")

args = parser.parse_args()

import src.algorithm_steps.aggregate_land_use_raster as aggregate_lu
import src.algorithm_steps.land_use_raster_creation as lurc
import src.algorithm_steps.calculate_region_land_use as calc_lu
import src.algorithm_steps.distribute_region_statistics as dist_stats


region_shapefile = args.region
pop_density_raster = args.population
region_stats_file = args.statistics

land_use_config = util.LandUseConfig(args.land_use)
land_use_shapefiles = land_use_config.shapefiles
landuse_mapping = land_use_config.mapping
scale_factors = land_use_config.scale_factors
land_use_encodings = land_use_config.encodings

temp_directory = args.temp
output_folder = args.out

num_land_use_bands = len(landuse_mapping)
resolution = land_use_config.resolution

#paths
rasterized_lu_folder = path.join(temp_directory, "land_use_rasters_10m")
merged_lu_raster = path.join(temp_directory, "merged_land_use_10m.tif")

land_use_aggregated = path.join(temp_directory, "land_use_{resolution}m.tif".format(resolution = resolution))

land_use_clipped = path.join(temp_directory, "land_use_{resolution}m_clipped.tif".format(resolution = resolution))

region_id_raster = path.join(temp_directory, "region_id_{resolution}m.tif".format(resolution = resolution))

regions_with_stats = path.join(temp_directory, "regions_with_stats")

pop_area_coverage_raster = path.join(temp_directory, "population_coverage_raster.tif")
emp_area_coverage_raster = path.join(temp_directory, "employment_coverage_raster.tif")

pop_raster_file = path.join(output_folder, "population_{resolution}m.tif".format(resolution = resolution))
emp_raster_file = path.join(output_folder, "employment_{resolution}m.tif".format(resolution = resolution))
merged_output_file = path.join(output_folder, "pop_emp_sum_{resolution}m.tif".format(resolution = resolution))


#step flags
CLEAR_DIRS = True
ENCODE_LAND_USE_VALUES = True #we already have encoded values in the shapefile
CREATE_LAND_USE_RASTERS = True
MERGE_LAND_USE_RASTERS = True
AGGREGATE_LAND_USE_RASTERS = True
CLIP_LAND_USE_RASTERS = True
BUILD_REGION_ID_RASTER = True

ADD_REGION_STATS = True

BUILD_POPULATION_RASTER = True
BUILD_EMPLOYMENT_RASTER = True

MERGE_POP_EMP_RASTERS = True
RUN_CHECKING = args.check

if CLEAR_DIRS:
    #clear temp directory
    shutil.rmtree(temp_directory, ignore_errors=True)
    os.mkdir(temp_directory)

    shutil.rmtree(output_folder, ignore_errors=True)
    os.mkdir(output_folder)

if ENCODE_LAND_USE_VALUES:
    #encode land use values to new shapefile
    encoded_lu_folder = path.join(temp_directory, "encoded_landuse")
    os.mkdir(encoded_lu_folder)
    print land_use_encodings
    lurc.encode_land_use_shapefiles(land_use_shapefiles, land_use_encodings, encoded_lu_folder)
    #
else:
    encoded_lu_folder = land_use_shapefiles

if CREATE_LAND_USE_RASTERS:
    #convert land use shapefile to raster
    print("\nconvert land use shapefile to raster...")
    os.mkdir(rasterized_lu_folder)
    lurc.create_land_userasters(encoded_lu_folder, rasterized_lu_folder, "Siedlung")

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

if ADD_REGION_STATS:
    #calc region land_use stats
    print("\ncalc region land_use stats")
    calc_lu.add_region_stats(region_shapefile, region_stats_file, ['pop_2008','emp_2008'], regions_with_stats)

if BUILD_POPULATION_RASTER:
    #calc region land_use stats
    print("\nbuild population raster -> to output folder")
    #TODO: analyse pop_density raster, and trim and fit to region and resolution if needed

    dist_stats.build_pop_raster(regions_with_stats,
                                pop_density_raster,
                                region_id_raster,
                                pop_area_coverage_raster, [1])

    dist_stats.distribute_region_statistics(regions_with_stats, "pop_2008",
                                            pop_area_coverage_raster, region_id_raster, pop_raster_file)


#build pop and employment rasters -> to output folder

if BUILD_EMPLOYMENT_RASTER:
    print("\nbuild employment raster -> to output folder, using scale factors:", scale_factors['employment'])
    dist_stats.build_emp_raster(regions_with_stats,
                                land_use_clipped,
                                region_id_raster,
                                emp_area_coverage_raster, scale_factors['employment'])

    dist_stats.distribute_region_statistics(regions_with_stats, "emp_2008",
                                            emp_area_coverage_raster, region_id_raster, emp_raster_file)

#merge pop and employment rasters -> to output folder
if MERGE_POP_EMP_RASTERS:
    dist_stats.add_rasters(pop_raster_file, emp_raster_file, merged_output_file)


if RUN_CHECKING:
    dist_stats.check_raster_output(regions_with_stats, pop_raster_file, ['pop_2008'])
    dist_stats.check_raster_output(regions_with_stats, emp_raster_file, ['emp_2008'])
    dist_stats.check_raster_output(regions_with_stats, merged_output_file, ['pop_2008', 'emp_2008'])





