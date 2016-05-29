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
from collections import OrderedDict
from src import util

def distribute_region_statistics(region_shapefile, land_use_raster_file, region_raster_file, output_file, land_use_categories):
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


def build_region_stats_lookup_table(region_shapefile):

    with fiona.open(region_shapefile, 'r') as region_features:

        #print list(region['properties'])[0], list(region['properties'])[1:]
        #print region_features[0]['properties']
        region_attrs = [region['properties'].items() for region in region_features]
        #print region_attrs
        stat_dict = {attrs[0][1] : OrderedDict(attrs[1:]) for attrs in region_attrs}

        #print stat_dict
    return stat_dict

if __name__ == "__main__":

    land_use_categories = util.load_land_use_mapping()
    RUN_DISTRIBUTE = True
    if RUN_DISTRIBUTE:
        distribute_region_statistics(
                                 "../../output/regions_with_land_use",
                                "../../data/land_use/land_use_100m_clipped.tif",
                                 "../../data/regional/region_raster.tif",
                                 "../../output/regions_with_land_use",
                                 "../../output/population_100m.tif",
                                 land_use_categories)