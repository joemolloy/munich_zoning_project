#!/usr/bin/python
# -*- coding: utf-8 -*-


import fiona
import rasterstats
import sys
from itertools import repeat
from collections import OrderedDict
from src import util
import csv

sys.path.append('../')

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


if __name__ == "__main__":
    Config = util.load_program_config()

    land_use_categories = util.load_land_use_mapping()

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




