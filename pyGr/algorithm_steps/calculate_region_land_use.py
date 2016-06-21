#!/usr/bin/python
# -*- coding: utf-8 -*-

import fiona
import rasterstats
from itertools import repeat
import csv

import rasterio
def add_region_stats(region_shapefile, region_statistics_file, include_fields, output_shapefile):

    (headers, region_stats) = csv_to_dict_utf8(region_statistics_file, ',', include_fields)
    if headers != include_fields:
        raise Exception("required columns are not in csv file:", ",".join(headers))

    with fiona.open(region_shapefile, 'r') as region_shapes:

        schema = {'geometry': 'Polygon',
                'properties': [ ('AGS_Int', 'int'), ('GEN', 'str'), ('Area', 'float')]}

        #create land use properties for new schema (will be percentages)
        stats_properties = zip(headers, repeat('float'))
        schema['properties'].extend(stats_properties)

        print schema

        with fiona.open(
                     output_shapefile, 'w',
                     driver=region_shapes.driver,
                     crs=region_shapes.crs,
                     schema=schema) as c:
            for region in region_shapes:
                old_properties = region['properties']
                region_id = region['properties']['AGS_Int']

                new_properties = {
                    'GEN': old_properties['GEN'],
                    'Area': old_properties['Shape_Area'],
                    'AGS_Int': region_id,
                }

                if region_id in region_stats:
                    new_properties.update(region_stats[region_id])
                else:
                    new_properties.update(zip(headers, repeat(0)))

                region['properties'] = new_properties

                c.write(region)

def calculate_region_land_use(region_shapefile, land_use_raster_multi_band,
                              region_statistics_file, output_shapefile, land_use_categories):

    include_fields = ['pop_2008','emp_2008']
    (headers, region_stats) = csv_to_dict_utf8(region_statistics_file, ',', include_fields)
    print "land use from:", land_use_raster_multi_band

    with fiona.open(region_shapefile, 'r') as region_shapes:
        indexed_land_use_categories = [(float(i), x) for (i,x) in enumerate(land_use_categories)]

        print indexed_land_use_categories
        #print land_use_raster_single_band
        with rasterio.open(land_use_raster_multi_band) as src:
            affine = src.affine
            a,b,c,d,e = src.read()

        zs_by_band = [rasterstats.zonal_stats(region_shapefile, array, affine=affine,
                                            stats=['sum'], geojson_out=True)
                         for array in [a,b,c,d,e]]

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

                    if value:
                        new_properties[category] = zs_by_band[band][i]['properties']['sum'] * 100
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
    return (filtered_headers, csv_dict)



