import rasterio
import numpy as np
import fiona
from collections import OrderedDict

def distribute_region_statistics(region_shapefile, key, density_raster_file, region_raster_file, output_file):
    with rasterio.open(density_raster_file, 'r') as density_raster:
        with rasterio.open(region_raster_file, 'r') as region_raster:
                region_stats = extract_region_value(region_shapefile, key)

                density_array_list = list(density_raster.read())

                (region_code_array,) = region_raster.read()
                print "region code array shape: ", region_code_array.shape
                print "region height:", region_raster.profile['height']

                regional_value_a = np.zeros(density_array_list[0].shape)
                print "region_value:", regional_value_a.shape, regional_value_a.dtype

                #for each land use band
                for (row,col), v in np.ndenumerate(region_code_array):
                    try:
                        region_id = int(region_code_array[row,col])
                        regional_value_a[row, col] = region_stats[region_id]
                    except KeyError:
                        regional_value_a[row, col] = 0

                result_a = sum([regional_value_a * d_a for d_a in density_array_list])

                profile = region_raster.profile
                profile.update(dtype=rasterio.float64)
                print "Writing", key, "to: ", output_file
                print profile
                with rasterio.open(output_file, 'w', **profile) as out:
                    out.write(result_a, indexes=1)


def extract_region_value(region_shapefile, key):

    with fiona.open(region_shapefile, 'r') as region_features:
        stat_dict = {r['properties']['AGS_Int']:r['properties'][key] for r in region_features}
    return stat_dict

def build_region_stats_lookup_table(region_shapefile):

    with fiona.open(region_shapefile, 'r') as region_features:

        region_attrs = [region['properties'].items() for region in region_features]
        stat_dict = {attrs[0][1] : OrderedDict(attrs[1:]) for attrs in region_attrs}
        return stat_dict
