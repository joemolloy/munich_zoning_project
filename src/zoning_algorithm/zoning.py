import sys, os
import src.util as util
import octtree
import ConfigParser
from fiona.crs import from_epsg
import rasterio

if __name__ == "__main__":
    Config = ConfigParser.ConfigParser(allow_no_value=True)

    if len(sys.argv) == 1 or not os.path.exists(sys.argv[1]):
        raise IOError("please supply a configuration file as a program arugment")
    Config.read(sys.argv[1])

    with rasterio.open(Config.get("Input", "combined_raster")) as r:
        raster_array = r.read(1)
        transform = r.affine
        zonesSaptialRef = r.crs

        regions = util.load_regions(Config)
        boundary = util.get_region_boundary(regions)
        envelope = util.get_square_envelope(raster_array.shape, transform)

        region_octtree = octtree.OcttreeNode(envelope, None, None)

        if Config.getboolean("Parameters", "solve_iteratively"):
            region_octtree = util.solve_iteratively(Config, region_octtree, regions, raster_array, r.affine)
        else:
            pop_threshold =  Config.getint("Parameters", "population_threshold")
            region_octtree = octtree.build_out_nodes(Config, region_octtree, regions, raster_array, r.affine, pop_threshold)

        util.calculate_final_values(Config, region_octtree)


    shapefile = Config.get("Land Use", "filename")
    inSpatialReference = from_epsg(Config.getint("Land Use", "EPSGspatialReference"))
    output_file = Config.get("Output", "filename")

    if Config.getboolean("Land Use", "calculate_land_use"):
        class_field = Config.get("Land Use", "class_field")
        #get land use values from config
        field_values = util.load_land_use_translations(2)
        util.run_tabulate_intersection(region_octtree, zonesSaptialRef, shapefile, inSpatialReference, class_field, field_values)
        util.save(output_file, zonesSaptialRef, region_octtree, include_land_use=True, field_values=field_values)

    else:
        util.save(output_file, zonesSaptialRef, region_octtree)
