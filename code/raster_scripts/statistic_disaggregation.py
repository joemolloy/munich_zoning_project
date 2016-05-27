
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
from shapely.geometry import shape

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

def calculate_region_land_use(region_shapefile, output_shapefile, land_use_raster_single_band, land_use_categories):
    with fiona.open(region_shapefile, 'r') as region_shapes:
        #for (band, lu_category) in land_use_categories:
        #    zs = rasterstats.zonal_stats(region_shapefile, land_use_raster,
        #                                      band = band, stats=['sum'])

        zs = rasterstats.zonal_stats(region_shapefile, land_use_raster_single_band,
                                            categorical=True, category_map=land_use_categories, geojson_out=True)

        print zs[1]

        schema = {'geometry': 'Polygon',
                'properties': [ ('AGS_Int', 'int'), ('GEN', 'str'), ('Area', 'float')]}

        land_use_properties = zip(zip(*land_use_categories)[1], repeat('int'))
        print land_use_properties
        schema['properties'].extend(land_use_properties)

        print schema

        with fiona.open(
         output_shapefile, 'w',
         driver=region_shapes.driver,
         crs=region_shapes.crs,
         schema=schema) as c:
                for region in zs:
                    old_properties = region['properties']

                    new_properties = {
                        'GEN': old_properties['GEN'],
                        'Area': old_properties['Shape_Area'],
                        'AGS_Int': old_properties['AGS_Int'],
                    }


                    total = 0
                    for (k,cat_name) in land_use_categories:
                        if (k, cat_name) in old_properties and k != 0:
                           value = old_properties[(k,cat_name)] * 100
                           new_properties[cat_name] = value
                           total += value
                        else:
                            new_properties[cat_name] = 0

                    new_properties['Remainder'] = new_properties['Area_calc'] - total


                    region['properties'] = new_properties

                    c.write(region)



Config = ConfigParser.ConfigParser(allow_no_value=True)

if len(sys.argv) == 1 or not os.path.exists(sys.argv[1]):
    raise IOError("please supply a configuration file as a program arugment")
Config.read(sys.argv[1])

cmap = [(float(k), v) for k,v in
            [tuple(Config.get("Class Values", c).split(',')) for c in Config.options("Class Values")]
        ]

print cmap

calculate_region_land_use("../../data/regional/Auspendler_in_Kernregion_25Proz_geglaettet",
                          "../../output/regions_with_land_use",
                          "../../data/land_use/land_use_merged_10m.tif", cmap)


def calculate_base_cell_disaggregation_factor(base_cells, regions, land_use_features):
    pass



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




