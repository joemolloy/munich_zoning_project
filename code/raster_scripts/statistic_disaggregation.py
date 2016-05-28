#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    distribute regional statistic by land use and area
    inputs:
        region shapefile with metrics
        land-use raster
        scaling factors

        given a raster cell, find all polygons that overlap (spatial index?)
        get the percentage coverage of each land use type
        based on inputed parameters
'''

import fiona
import rasterstats
import ConfigParser
import sys, os
from itertools import repeat
from shapely.geometry import Point
import numpy as np
from collections import OrderedDict

#CASE WHEN OBJART  = 'AX_Wohnbauflaeche' THEN 1
#	WHEN OBJART  =  'AX_FlaecheBesondererFunktionalerPraegung' THEN 2
#	WHEN OBJART  = 'AX_FlaecheGemischterNutzung' THEN 3
#	WHEN OBJART  =  'AX_IndustrieUndGewerbeflaeche' THEN 4
#	ELSE 0
# END
values = ["remainder",
 'AX_Wohnbauflaeche',
 'AX_FlaecheBesondererFunktionalerPraegung',
 'AX_FlaecheGemischterNutzung',
 'AX_IndustrieUndGewerbeflaeche',
 'AX_SportFreizeitUndErholungsflaeche']

#land_use_categories: (band, name)

#
def calculate_region_land_use(region_shapefile, land_use_raster_single_band,
                              region_statistics_file, output_shapefile, land_use_categories):

    include_fields = ['pop_2008','emp_2008']
    (headers, region_stats) = csv_to_dict_utf8(region_statistics_file, ',', include_fields)
    print region_stats

    with fiona.open(region_shapefile, 'r') as region_shapes:
        #for (band, lu_category) in land_use_categories:
        #    zs = rasterstats.zonal_stats(region_shapefile, land_use_raster,
        #                                      band = band, stats=['sum'])
        indexed_land_use_categories = [(float(i), x) for (i,x) in enumerate(land_use_categories)]

        zs = rasterstats.zonal_stats(region_shapefile, land_use_raster_single_band,
                                            categorical=True, category_map=indexed_land_use_categories, geojson_out=True)

        schema = {'geometry': 'Polygon',
                'properties': [ ('AGS_Int', 'int'), ('GEN', 'str'), ('Area', 'float'), ('Area_covered', 'float')]}

        #create land use properties for new schema (will be percentages)
        land_use_properties = zip(land_use_categories, repeat('float'))
        stats_properties = zip(headers, repeat('float'))
        print land_use_properties
        schema['properties'].extend(land_use_properties)
        schema['properties'].extend(stats_properties)

        print schema

        with fiona.open(
                     output_shapefile, 'w',
                     driver=region_shapes.driver,
                     crs=region_shapes.crs,
                     schema=schema) as c:
            for region in zs:
                old_properties = region['properties']
                region_id = region['properties']['AGS_Int']

                new_properties = {
                    'GEN': old_properties['GEN'],
                    'Area': old_properties['Shape_Area'],
                    'AGS_Int': region_id,
                }

                total_land_used = sum([old_properties[key]
                                       for key in indexed_land_use_categories
                                       if key[1] != "Remainder" and key in old_properties])

                for (k, cat_name) in indexed_land_use_categories:
                    if (k,cat_name) in old_properties and cat_name != "Remainder":
                        value = old_properties[(k, cat_name)]
                        new_properties[cat_name] = value * 100
                        #print new_properties[cat_name]
                    else:
                        new_properties[cat_name] = 0

                new_properties['Area_covered'] = total_land_used * 100
                new_properties['Remainder'] = new_properties['Area'] - new_properties['Area_covered']

                if region_id in region_stats:
                    new_properties.update(region_stats[region_id])
                else:
                    #print "fail on:", region_id
                    new_properties.update(zip(headers, repeat(0)))

                region['properties'] = new_properties

                c.write(region)



#given a land_use array + transformation, mapping from region to land-uses and values, bounds of new array,

# {region : {key : value} }
import math
import rasterio
import csv, codecs
from itertools import izip


def distribute_region_statistics(land_use_raster_file, region_raster_file, region_shapefile, output_file, cmap):
    with rasterio.open(land_use_raster_file, 'r') as land_use_raster:
        with rasterio.open(region_raster_file, 'r') as region_raster:
                region_stats = build_region_stats_lookup_table(region_shapefile)


                #trim land
                affine_LU = land_use_raster.profile['affine']
                affine_regions = region_raster.profile['affine']

                lu_array = land_use_raster.read()

                #move the bands to the third dimension to make calculations easier to work with
                #lu_array is the 100m raster of land use separated by bands. must be x100 to get land use in area.
                #need to make sure we move up from ubyte to uint32 to store larger values that we will sue
                cell_land_use_m2 = np.rollaxis(lu_array, 0, 3).astype(np.uint32) * 100
                print cell_land_use_m2.shape, cell_land_use_m2.dtype



                #remove remaining column
                REMAINDER_COL = 0
                cell_land_use_m2 = np.delete(cell_land_use_m2,REMAINDER_COL, axis=2)
                #repeat summed area value so that the divison against each band will work
                #cell_land_use_m2 = np.true_divide(
                #       cell_land_use_m2,
                #        np.atleast_3d(np.sum(cell_land_use_m2, axis=2))
                #)
                #cell_land_use_m2 = np.nan_to_num(cell_land_use_m2)

                print cell_land_use_m2[13:20,790:800,0]

                (region_code_array,) = region_raster.read()
                print "region code array shape: ", region_code_array.shape
                print "region height:", region_raster.profile['height']

                region_land_use_split_m2 = np.zeros(cell_land_use_m2.shape)
                region_population = np.zeros(cell_land_use_m2.shape)
                print "region_land_use_split_m2:", region_land_use_split_m2.shape, region_land_use_split_m2.dtype
                print "region_population:", region_population.shape, region_population.dtype

                for k in region_stats.keys():
                    region_stats[k]["cell_area"] = 0

                #for each land use band
                for (row,col,z), v in np.ndenumerate(cell_land_use_m2):
                    #if not math.isnan(v):
                        #TODO: auto clip land-use raster to region raster
                        #location region_id from region_raster
                        region_id = region_code_array[row,col]

                        #pull the regional land use percentage for each region
                        if region_id:
                            region_id = int(region_id)
                            land_use_type = land_use_categories[z+1] #row 0 is now land use type 1
                            pc_landuse = region_stats[region_id][land_use_type]
                            area_landuse = region_stats[region_id]["Area_cover"]

                            region_stats[region_id]["cell_area"] += v

                            value = pc_landuse # / area_landuse

                            if row in xrange(13,30) and col in xrange(790,800):
                                print (row, col), z, int(region_id), pc_landuse, area_landuse, "=", value

                            region_land_use_split_m2[row, col, z] = value
                            #assign population value
                            try:
                                region_population[row, col] = region_stats[region_id]['pop_2008']
                                #region_population[row, col] = 1000
                            except KeyError:
                                print region_id, region_stats[region_id]['GEN'], "not in pop/emp dataset"
                                region_population[row, col] = 0

                print region_land_use_split_m2[13:20,790:800,0]

                for k in region_stats.keys():
                    print region_stats[k]["Area_cover"], region_stats[k]["cell_area"], region_stats[k]["Area_cover"] - region_stats[k]["cell_area"]

                #print lu_agg
                scale_factors = [0.7,0.05,0,0.01,0]
                #scale_factors = [1.0,1.0,1.0,1.0,1.0]

                scaling_vector = np.array(scale_factors) / sum(scale_factors)
                print "calculating population raster with scale vector:", scaling_vector
                region_population_land_use_scaled = np.atleast_3d(region_population) * scaling_vector

                with np.errstate(divide='ignore', invalid='ignore'):
                    cell_lu_pc = np.true_divide(cell_land_use_m2,region_land_use_split_m2)
                    cell_lu_pc[cell_lu_pc == np.inf] = 0
                    cell_lu_pc = np.nan_to_num(cell_lu_pc)

                cell_lu_population = cell_lu_pc * region_population_land_use_scaled

                summed_population = np.sum(cell_lu_population, axis=2)

                result_int = summed_population.astype(np.float32)
                print "result shape:", result_int.shape

        #        for x in np.nditer(result_int):
        #            if x != 0:
        #                print x

                #result = np.ones(result.shape, dtype=np.float64)

                # grid_percentage * regional_percentage * regional_population_value * scalar

                #for (row,col), v in np.ndenumerate(result):
                #    if v > 0:
                #        print (row, col), v

                profile = region_raster.profile
                profile.update(dtype=rasterio.float32)
                #profile.update(dtype=rasterio.ubyte)
                print "Writing to: ", output_file
                print profile
                with rasterio.open(output_file, 'w', **profile) as out:
                    out.write(result_int, indexes=1)

def check_raster_output(region_shapefile, population_raster):
    zs = rasterstats.zonal_stats(region_shapefile, population_raster, stats=['sum'])
    with fiona.open(region_shapefile) as regions:
        for (region, stat) in zip(regions, zs):
            try:
                actual = float(region['properties']['pop_2008'])
                calcd = float(stat['sum'])
                print region['properties']['AGS_Int'], actual, calcd, actual-calcd, float(actual-calcd)/actual
            except TypeError:
                print "no value for ", region['properties']['AGS_Int']


def build_region_stats_lookup_table(region_shapefile):

    with fiona.open(region_shapefile, 'r') as region_features:

        #print list(region['properties'])[0], list(region['properties'])[1:]
        #print region_features[0]['properties']
        region_attrs = [region['properties'].items() for region in region_features]
        #print region_attrs
        stat_dict = {attrs[0][1] : OrderedDict(attrs[1:]) for attrs in region_attrs}

        #print stat_dict
    return stat_dict

def csv_to_dict_utf8(csv_file, delimiter, include_fields):
    land_use_stats = csv.reader(open(csv_file, 'rb'), dialect=csv.excel)
    headers = [unicode(x, 'utf-8') for x in land_use_stats.next()[1:]] #ignore index header (AGS_Int)
    filtered_headers = [x for x in headers if x in include_fields]
    csv_dict = {}

    AGS_LEN = 7

    for row in land_use_stats:
        unicode_row = [unicode(x, 'utf-8') for x in row]
        index_str = str(unicode_row[0])
        index = int(index_str + '0'*(AGS_LEN - len(index_str))) #9 --> 9000000
        csv_dict[index] = {}
        for (header, col) in zip(headers, unicode_row[1:]):
            if header in include_fields:
                try:
                    csv_dict[index][header] = float(col)
                except ValueError:
                    csv_dict[index][header] = col

        #print index, csv_dict[index]
    print filtered_headers
    return (filtered_headers, csv_dict)

Config = ConfigParser.ConfigParser(allow_no_value=True)

if len(sys.argv) == 1 or not os.path.exists(sys.argv[1]):
    raise IOError("please supply a configuration file as a program arugment")
Config.read(sys.argv[1])

land_use_categories = [Config.get("Class Values", c).split(',')[1] for c in Config.options("Class Values")]

print "Working with land use categories:", land_use_categories

RUN_CALC_REGION_LU = False
RUN_DISTRIBUTE = True
RUN_CHECKING = True


if RUN_CALC_REGION_LU:
    calculate_region_land_use("../../data/regional/Auspendler_in_Kernregion_25Proz_geglaettet",
                              "../../data/land_use/land_use_merged_10m.tif",
                              "../../data/regional/region_pop_employment_data_clean.csv",
                              "../../output/regions_with_land_use",
                              land_use_categories)

if RUN_DISTRIBUTE:
    distribute_region_statistics("../../data/land_use/land_use_100m_clipped.tif",
                             "../../data/regional/region_raster.tif",
                             "../../output/regions_with_land_use",
                             "../../output/population_100m.tif",
                             land_use_categories)
if RUN_CHECKING:
    check_raster_output("../../data/regional/regions_lu_pop_emp.geojson", "../../output/population_100m.tif")



#
# for each 'zone building block', provide a scaling factor for that block
#
# for each municipality:
#   tablulate the m^2 coverage of each land use type
#   store total land use coverage (m^2) for that municipality
#
# create building blocks (at minimum resolution), and split at municipality regions
# link building blocks as children of a municipality
#
# for each building block:
#   get m^2 for each land use type
#   disaggregation factor is (raster_land_use / municipality_land_use)
#
# using config scaling factors, distribute population accordingly


# ????possibly use detailed population data to determine scaling factors?




