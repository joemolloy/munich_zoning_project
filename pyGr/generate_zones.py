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
        zonesSaptialRef = r.crs

        regions = region_ops.load_regions(Config)
        boundary = region_ops.get_region_boundary(regions)
        envelope = region_ops.get_square_envelope(raster_array.shape, transform)

        region_octtree = octtree.OcttreeNode(envelope, None, None)

        if Config.getboolean("Parameters", "solve_iteratively"):
            region_octtree = iteration.solve_iteratively(Config, region_octtree, regions, raster_array, r.affine)
        else:
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

