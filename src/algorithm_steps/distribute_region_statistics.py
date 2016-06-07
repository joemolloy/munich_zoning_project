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


import rasterio
import fiona
import numpy as np
import rasterstats
from collections import OrderedDict
from src import util
from os import path
import subprocess

def build_pop_raster(region_shapefile, pop_density_raster_file, region_raster_file, output_file, scale_factors):
    build_region_density_raster(region_shapefile, "population", pop_density_raster_file, region_raster_file, output_file, scale_factors)

def build_emp_raster(region_shapefile, land_use_clipped, region_raster_file, output_file, scale_factors):
    build_region_density_raster(region_shapefile, "employment", land_use_clipped, region_raster_file, output_file, scale_factors)

#break the rasterisation down into steps. first.
#first build a scaled density by region raster. Then we will multiply this by the regional values
def build_region_density_raster(region_shapefile, name, value_raster_file, region_raster_file, output_file, scale_factors):
    with rasterio.open(value_raster_file, 'r') as value_raster:
        with rasterio.open(region_raster_file, 'r') as region_raster:

                (region_code_array,) = region_raster.read()

                resolution = 100
                num_bands = len(scale_factors)
                density_arrays = []

                for i,f in enumerate(scale_factors):
                    #clip values so that smallest value is positive
                    value_array = np.clip(value_raster.read(i+1), 0, None)

                    zs = rasterstats.zonal_stats(region_shapefile,
                                                 value_array,
                                                 affine=value_raster.affine,
                                                 band=i+1, stats=['sum', 'count'],
                                                 geojson_out=True)

                    region_value_sums = {z['properties']['AGS_Int']: z['properties'] for z in zs}

                    density_array = np.zeros(value_array.shape)

                    #for each land use band
                    for (row,col), v in np.ndenumerate(value_array):
                        try:
                            region_id = int(region_code_array[row,col])
                            region_sum = region_value_sums[region_id]['sum']
                            #if value_array[row, col]:
                            #    print region_id, ":", region_sum, region_value_sums[region_id]['count']
                            #    print "\tv:", (row, col), value_array[row, col]

                            density_array[row, col] = (float(value_array[row, col]) / region_sum) * f
                            #if value_array[row, col] < 0 or (region_sum * f) < 0:
                            #    print "(v, region, f):", value_array[row, col], region_sum, f
                            #print (row, col), float(value_array[row, col]) / (region_sum * f)

                        except (KeyError, IndexError, TypeError, ZeroDivisionError):
                            density_array[row, col] = 0


                    density_arrays.append(density_array)

                profile = region_raster.profile
                profile.update(dtype=rasterio.float64)
                profile.update(count=num_bands)
                print "Writing population to: ", output_file
                print profile
                with rasterio.open(output_file, 'w', **profile) as out:
                    for band in range(num_bands):
                        out.write(density_arrays[band], indexes=band+1)

def distribute_region_statistics(region_shapefile, key, density_raster_file, region_raster_file, output_file):
    with rasterio.open(density_raster_file, 'r') as density_raster:
        with rasterio.open(region_raster_file, 'r') as region_raster:
                region_stats = extract_region_value(region_shapefile, key)

                resolution = 100

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
                #profile.update(dtype=rasterio.ubyte)
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

        #print list(region['properties'])[0], list(region['properties'])[1:]
        #print region_features[0]['properties']
        region_attrs = [region['properties'].items() for region in region_features]
        #print region_attrs
        stat_dict = {attrs[0][1] : OrderedDict(attrs[1:]) for attrs in region_attrs}

        #print stat_dict
    return stat_dict


import rasterstats
from math import sqrt, pow
def check_raster_output(region_shapefile, stats_raster, fields):
    zs = rasterstats.zonal_stats(region_shapefile, stats_raster, stats=['sum'])
    with fiona.open(region_shapefile) as regions:
        results = []
        for (region, stat) in zip(regions, zs):
            try:
                actual=sum([float(region['properties'][f]) for f in fields])
                calculated = (float(stat['sum']))
                results.append((actual, calculated))
            except TypeError:
                #print "no value for ", region['properties']['AGS_Int']
                results.append((0,0))


    print "results for", stats_raster,"..."
    print results
    actuals, calcd = zip(*results)
    print "\t actual:", "{:,}".format(sum(actuals))
    print "\t calculated:", "{:,}".format(sum(calcd))
    print "\t difference:", "{:,}".format(sum(actuals) - sum(calcd))
    print "\t RMSE:", "{:,}".format(sqrt(sum([pow(a-b,2) for (a,b) in results]) / len(results)))


def add_rasters(a_file,b_file, outputfile):
    with rasterio.open(a_file) as a:
        with rasterio.open(b_file) as b:
            profile = a.profile
            with rasterio.open(outputfile, 'w', **profile) as out:
                c = a.read(1) + b.read(1)
                out.write(c, indexes=1)
  #  cmd = ["gdal_calc.py",
  ##         "-A", a_file,
  #         "-B", b_file,
  #         "--outfile={outfile}".format(outfile = outputfile),
  #         '--calc="A+B"']

#    print cmd
 #   subprocess.check_call(cmd)


if __name__ == "__main__":

    land_use_categories = util.load_land_use_mapping(1)
    RUN_DISTRIBUTE = False
    RUN_CHECKING = True

    if RUN_DISTRIBUTE:
        distribute_region_statistics(
                                 "../../output/regions_with_land_use",
                                "../../data/land_use/land_use_100m_clipped.tif",
                                 "../../data/regional/region_raster.tif",
                                 "../../output/regions_with_land_use",
                                 "../../output/population_100m.tif",
                                 land_use_categories)

    if RUN_CHECKING:
        #check_raster_output("../../data/regional/regions_lu_pop_emp.geojson", "../../output/population_100m.tif")
        #check_raster_output("../../data/temp/regions_with_land_use", "../../output/population_100m.tif")
        check_raster_output("../../data/temp/regions_with_land_use", "../../data/test_output/population_100m.tif")

