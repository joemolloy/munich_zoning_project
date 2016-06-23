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
from math import sqrt

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

                num_bands = len(scale_factors)
                density_arrays = []

                for i,f in enumerate(scale_factors):
                    #clip values so that smallest value is positive
                    value_array = np.clip(value_raster.read(i+1), 0, None)

                    zs = rasterstats.zonal_stats(region_shapefile,
                                                 value_array,
                                                 affine=value_raster.affine,
                                                 band=i+1,
                                                 stats=['sum', 'count'],
                                                 geojson_out=True)

                    region_value_sums = {z['properties']['AGS_Int']: z['properties'] for z in zs}

                    density_array = np.zeros(value_array.shape)

                    #for each land use band
                    for (row,col), v in np.ndenumerate(value_array):
                        try:
                            region_id = int(region_code_array[row,col])
                            region_sum = region_value_sums[region_id]['sum']
                            density_array[row, col] = (float(value_array[row, col]) / region_sum) * f

                        except (KeyError, IndexError, TypeError, ZeroDivisionError):
                            density_array[row, col] = 0

                    density_arrays.append(density_array)

                profile = region_raster.profile
                profile.update(dtype=rasterio.float64)
                profile.update(count=num_bands)
                print "Writing", name, "to: ", output_file
                print profile
                with rasterio.open(output_file, 'w', **profile) as out:
                    for band in range(num_bands):
                        out.write(density_arrays[band], indexes=band+1)



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
    print "\t RMSE:", "{:,}".format(sqrt(sum([a-b**2 for (a,b) in results]) / len(results)))

def add_rasters(a_file,b_file, outputfile):
    with rasterio.open(a_file) as a:
        with rasterio.open(b_file) as b:
            profile = a.profile
            with rasterio.open(outputfile, 'w', **profile) as out:
                c = a.read(1) + b.read(1)
                out.write(c, indexes=1)

