import numpy as np
import os
import psycopg2
from zoning_algorithm.octtree import build_out_nodes
import rasterio
from rasterstats import zonal_stats
from affine import Affine
import ConfigParser
import fiona
from shapely.geometry import mapping, shape, box
from shapely.ops import cascaded_union

from pyproj import transform, Proj

def load_regions(Config):
    regions_file = Config.get("Regions", "filename")

    regions = []

    with fiona.open(regions_file) as src:  ##TODO: fix handling of multipolygons
        for f in src:
            #print f['geometry']['type']
            g = f['geometry']
            if f['geometry']['type'] != "Polygon":
                #split up mutli_polygon regions
                if f['geometry']['type'] == "MultiPolygon" :
                    for geom_part in shape(f['geometry']):
                        f2 = {'geometry': mapping(geom_part), 'properties': f['properties'].copy()}
                        regions.append(f2)
            elif f['geometry']['type'] == "Polygon":
                regions.append(f)

    return regions

def get_region_boundary(regions):
    return cascaded_union([shape(r['geometry']) for r in regions])

def get_square_envelope((rows, cols), affine):
    n = next_power_of_2(max(rows, cols))
    extra_r = n - rows
    extra_c = n - cols
    (minx, miny) = affine * (0,0)
    (maxx, maxy) = affine * (cols + extra_c, rows + extra_r)
    envelope = box(minx, miny, maxx, maxy)

    return envelope

def transform_fiona_polygon(f, p_in, p_out) :
    new_coords = []
    for ring in f['geometry']['coordinates']:
        #print ring
        x2, y2 = transform(p_in, p_out, *zip(*ring))
        new_coords.append(zip(x2, y2))
    f['geometry']['coordinates'] = new_coords

#Round up to next higher power of 2 (return x if it's already a power of 2).
#from http://stackoverflow.com/questions/1322510
def next_power_of_2(n):
    """
    Return next power of 2 greater than or equal to n
    """
    return 2**(n-1).bit_length()

def solve_iteratively(Config, region_octtree, regions, raster, raster_affine):
    ##
    # if num zones is too large, we need a higher threshold
    # keep a record of the thresholds that result in the nearest low, and nearest high
    # for the next step, take the halfway number between the two

    desired_num_zones = Config.getint("Parameters", "desired_num_zones")
    best_low = Config.getint("Parameters", "lower_population_threshold")
    best_high = Config.getint("Parameters", "upper_population_threshold")
    tolerance =  Config.getfloat("Parameters", "tolerance")

    step = 1
    solved = False
    num_zones = 0

    pop_threshold = (best_high - best_low) / 2


    while not solved: # difference greater than 10%
        print 'step %d with threshold level %d...' % (step, pop_threshold)
        region_octtree = build_out_nodes(Config, region_octtree, regions, raster, raster_affine, pop_threshold)
        num_zones = region_octtree.count_populated()
        print "\tnumber of cells:", num_zones
        print ''

        solved = abs(num_zones - desired_num_zones)/float(desired_num_zones) < tolerance
        if not solved:
            if num_zones > desired_num_zones:
                best_low = max (best_low, pop_threshold)
            else:
                best_high = min (best_high, pop_threshold)
            pop_threshold = (best_low + best_high) / 2

        step += 1

    print "Solution found!"
    print "\t%6d zones" % (num_zones)
    print "\t%6d threshold" % (pop_threshold)

    return region_octtree

def run_tabulate_intersection(zone_octtree, land_use_folder, class_field, field_values):
    print field_values

    #set value for each zones and class to zero
    for zone in zone_octtree.iterate():
        zone.landuse_pc = {}
        zone.landuse_area = {}
        for (field, class_alias) in field_values:
            zone.landuse_pc[class_alias] = 0
            zone.landuse_area[class_alias] = 0

    print "running intersection tabulation"

    print land_use_folder
    checked_features = set() #need to make sure that we dont double count features that are in two files (rely on unique OIDs)

    for folder in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, folder)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]

            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")
            tabulate_intersection(zone_octtree, full_sp_path, checked_features, class_field, field_values)

def tabulate_intersection(zone_octtree, shapefile, checked_features, class_field, field_values):
    #print "running intersection tabulation"
    (land_types, land_type_aliases) = zip(*field_values)
    with fiona.open(shapefile) as src:
        print '\t' , shapefile, '...'

        for feature in src:
            oid = feature['properties']['OID']
            if oid not in checked_features:
                checked_features.add(oid)
                #need to check the OID. If it has already been checked in another land use file, ignore.
                #get class
                poly_class = feature['properties'][class_field].lower()
                if poly_class in land_types: #*zip means unzip. Only work with land types we want
                    class_alias = land_type_aliases[land_types.index(poly_class)] #make faster?
                    #transform
                    poly = shape(feature['geometry'])

                    matches = find_intersections(zone_octtree, poly)

                    for zone in matches:
                        #print zone.index, class_name, percentage
                        intersection = zone.polygon.intersection(poly)
                        pc_coverage = intersection.area / zone.polygon.area
                        zone.landuse_pc[class_alias] += pc_coverage
                        zone.landuse_area[class_alias] += intersection.area

def find_intersections(node, poly):
    matches = []

    if node.polygon.intersects(poly):
        try:
            for child in node.getChildren():
                matches.extend(find_intersections(child, poly))
        except AttributeError: #octtreeleaf
            matches.append(node)

    return matches

def save(filename, outputSpatialReference, octtree, include_land_use = False, field_values = None):
    print "saving zones with land use to:", filename

    schema = {'geometry': 'Polygon',
                'properties': [('id', 'int'), ('Pop+Emp', 'int'), ('Population', 'int'),
                               ('Employment', 'int'), ('Area', 'float'), ('AGS', 'int')]}

    if include_land_use:
        for (f, alias) in field_values:
            schema['properties'].append((alias,'float'))
        schema['properties'].append(('remainder', 'float'))

    with fiona.open(
         filename, 'w',
         driver="ESRI Shapefile",
         crs=outputSpatialReference,
         schema=schema) as c:

        for i, zone in enumerate(octtree.iterate()):

            properties = {
                'id': i+1,
                'Pop+Emp': zone.combined,
                'Population': zone.population,
                'Employment': zone.employment,
                'Area': zone.polygon.area,
                'AGS': zone.region['properties']['AGS_Int']
            }
            if include_land_use:
                land_use_remainder = 1.0
                for (f, alias) in field_values:
                    land_use_remainder -= zone.landuse_pc[alias]
                    properties[alias] = zone.landuse_pc[alias]
                properties['remainder'] = land_use_remainder

            c.write({
                'geometry': mapping(zone.polygon),
                'properties': properties
            })

def load_config(filename):
    Config = ConfigParser.ConfigParser(allow_no_value=True)
    if not os.path.exists(filename):
        raise IOError("Config file %s does not exist" % filename)
    else:
        Config.read(filename)
        return Config

class LandUseConfig:
    def __init__(self, filename):
        self.config = load_config(filename)
        self.class_field = self.config.get("Class Field", "Field")
        self.resolution = self.config.getint("Input", "desired_raster_resolution")
        self.shapefiles = self.config.get("Input", "folder")
        self.mapping = [self.config.get("Class Values", c) for c in self.config.options("Class Values")]
        self.scale_factors = load_scaling_factors(self.config)
        self.encodings = {c : i+1 for (i,c) in enumerate(self.config.options("Class Values"))}
        self.translations = [(c, self.config.get("Class Values", c)) for c in self.config.options("Class Values")]

        #TODO: check all inputs

def load_scaling_factors(config):
    factors = {}
    for key in config.options("Scaling Factors"):
        try:
            values_strs = config.get("Scaling Factors", key).split(",")
            values = map(float,values_strs)
            assert np.isclose(sum(values),1.0), "Scaling factors must sum to 1.0"
            factors[key] = values
        except:
            raise Exception("Please provide valid scaling factors that add to 1.0, ie: '0.2,0.2,0.2,0.2'")
    return factors

def calculate_final_values(Config, zone_octtree):
    with rasterio.open(Config.get("Input","combined_raster")) as combined_rst:
        combined_array = combined_rst.read(1)
        combined_affine = combined_rst.affine
    with rasterio.open(Config.get("Input","pop_raster")) as pop_rst:
        pop_array = pop_rst.read(1)
        pop_affine = combined_rst.affine
    with rasterio.open(Config.get("Input","emp_raster")) as emp_rst:
        emp_array = emp_rst.read(1)
        emp_affine = emp_rst.affine

    for zone in zone_octtree.iterate():
        zs_cmb = zonal_stats(zone.polygon, combined_array, affine=combined_affine, stats='sum')[0]['sum']
        zs_pop = zonal_stats(zone.polygon, pop_array, affine=pop_affine, stats='sum')[0]['sum']
        zs_emp = zonal_stats(zone.polygon, emp_array, affine=emp_affine, stats='sum')[0]['sum']

        zone.combined = zs_cmb
        zone.population = zs_pop
        zone.employment = zs_emp


