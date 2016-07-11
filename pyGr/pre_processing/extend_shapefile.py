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



