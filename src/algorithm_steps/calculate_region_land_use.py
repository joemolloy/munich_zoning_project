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


#land_use_categories: (band, name)

#
import rasterio

def calculate_region_land_use(region_shapefile, land_use_raster_multi_band,
                              region_statistics_file, output_shapefile, land_use_categories):

#    with rasterio.open(land_use_raster_multi_band) as lu_mb:
#       a,b,c,d,e = lu_mb.read()
#        affine = lu_mb.affine
#        land_use_raster_single_band = (a+b+c+d+e).astype(rasterio.uint32)

#    print land_use_raster_single_band.shape, land_use_raster_single_band

#    print land_use_raster_single_band[13:20,790:800]

    include_fields = ['pop_2008','emp_2008']
    (headers, region_stats) = csv_to_dict_utf8(region_statistics_file, ',', include_fields)
    print "land use from:", land_use_raster_multi_band

    with fiona.open(region_shapefile, 'r') as region_shapes:
        #for (band, lu_category) in land_use_categories:
        #    zs = rasterstats.zonal_stats(region_shapefile, land_use_raster,
        #                                      band = band, stats=['sum'])
        indexed_land_use_categories = [(float(i), x) for (i,x) in enumerate(land_use_categories)]

        print indexed_land_use_categories
        #print land_use_raster_single_band

        with rasterio.open(land_use_raster_multi_band) as src:
            affine = src.affine
            a,b,c,d,e = src.read()

        zs_by_band = [rasterstats.zonal_stats(region_shapefile, array, affine=affine,
                                            stats=['sum'], geojson_out=True)
                         for array in [a,b,c,d,e]]

        for zs in zs_by_band:
            print zs[-1]['properties']['sum']

        print len(zs_by_band)


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
            for (i, region) in enumerate(zs_by_band[0]):
                old_properties = region['properties']
                region_id = region['properties']['AGS_Int']

                new_properties = {
                    'GEN': old_properties['GEN'],
                    'Area': old_properties['Shape_Area'],
                    'AGS_Int': region_id,
                }

                total_land_used = sum([zs[i]['properties']['sum'] for zs in zs_by_band
                                       if zs[i]['properties']['sum']] )

                for band, zs in enumerate(zs_by_band):
                    value = zs_by_band[band][i]['properties']['sum']
                    category = land_use_categories[band+1]
                    #print region_id, category, band, value

                    if value:
                        new_properties[category] = zs_by_band[band][i]['properties']['sum'] * 100
                        #print new_properties[cat_name]
                    else:
                        new_properties[category] = 0

                new_properties['Area_covered'] = total_land_used  * 100
                new_properties['Remainder'] = new_properties['Area'] - new_properties['Area_covered']

                if region_id in region_stats:
                    new_properties.update(region_stats[region_id])
                else:
                    #print "fail on:", region_id
                    new_properties.update(zip(headers, repeat(0)))

                region['properties'] = new_properties

                c.write(region)


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
    print "open csv file:", csv_file
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




