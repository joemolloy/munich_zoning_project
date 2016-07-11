import sys, os
from pyGr.zoning_algorithm import octtree
import ConfigParser
import rasterio
from pyGr.common import region_ops
from pyGr.zoning_algorithm import iteration, helper_functions, tabulation
from pyGr.common import config


if __name__ == "__main__":
    Config = ConfigParser.ConfigParser(allow_no_value=True)

    if len(sys.argv) == 1 or not os.path.exists(sys.argv[1]):
        raise IOError("please supply a configuration file as a program arugment")
    Config.read(sys.argv[1])

    with rasterio.open(Config.get("Input", "combined_raster")) as r:
        raster_array = r.read(1)
        transform = r.affine
        zonesSaptialRef = r.crs.to_dict()

        regions = region_ops.load_regions(Config)
        boundary = region_ops.get_region_boundary(regions)
        envelope = region_ops.get_square_envelope(raster_array.shape, transform)

        region_octtree = octtree.OcttreeNode(envelope, None, None)

        if Config.get("Parameters", "mode") == 'Trend':
                region_octtree = iteration.model_zones_vs_threshold(Config, region_octtree, regions, raster_array, r.affine)
        else:
            if Config.get("Parameters", "mode") == 'Iterative':
                region_octtree = iteration.solve_iteratively(Config, region_octtree, regions, raster_array, r.affine)
            if Config.get("Parameters", "mode") == 'Once':
                pop_threshold =  Config.getint("Parameters", "population_threshold")
                region_octtree = octtree.build_out_nodes(Config, region_octtree, regions, raster_array, r.affine, pop_threshold)

            helper_functions.calculate_final_values(Config, region_octtree)


            output_file = Config.get("Output", "filename")

            if Config.getboolean("Land Use", "calculate_land_use"):
                lu_config = config.LandUseConfig(sys.argv[2])
                class_field = lu_config.class_field
                shapefiles = lu_config.shapefiles
                #get land use values from config
                field_values = lu_config.translations
                tabulation.run_tabulate_intersection(region_octtree, shapefiles, class_field, field_values)
                helper_functions.save(output_file, zonesSaptialRef, region_octtree, include_land_use=True, field_values=field_values)

            else:
                helper_functions.save(output_file, zonesSaptialRef, region_octtree)

            if Config.getboolean('Regions', 'validate_zones'):
                identifier = Config.get('Regions', 'identifier')
                pop_field = Config.get('Regions', 'population_field')
                emp_field = Config.get('Regions', 'employment_field')
                helper_functions.validate_zones( Config.get("Regions", "filename"), identifier, pop_field, emp_field, output_file)

