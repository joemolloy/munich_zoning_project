import numpy as np
import os
import psycopg2
from zoning_algorithm.octtree import OcttreeLeaf, OcttreeNode, build_out_nodes
from rasterstats import zonal_stats
from affine import Affine

import fiona
from shapely.geometry import mapping, shape


from pyproj import transform, Proj
from shapely.ops import cascaded_union
from shapely.geometry import LineString, Polygon


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

def transform_fiona_polygon(f, p_in, p_out) :
    new_coords = []
    for ring in f['geometry']['coordinates']:
        #print ring
        x2, y2 = transform(p_in, p_out, *zip(*ring))
        new_coords.append(zip(x2, y2))
    f['geometry']['coordinates'] = new_coords

def create_octtree(regions):
    boundary = cascaded_union(regions)
    ot = None
    children = [OcttreeNode(region,[], ot) for region in regions]
    ot = OcttreeNode(boundary, None, None)
    return ot

#Round up to next higher power of 2 (return x if it's already a power of 2).
#from http://stackoverflow.com/questions/1322510
def next_power_of_2(n):
    """
    Return next power of 2 greater than or equal to n
    """
    return 2**(n-1).bit_length()

def solve_iteratively(Config, region_octtree, regions, pop_array, affine):
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
        region_octtree = build_out_nodes(Config, region_octtree, regions, pop_array, affine, pop_threshold)
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

def load_data2(Config, min_x, min_y, max_x, max_y):
    database_string = Config.get("Input", "databaseString")
    if database_string:
        conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
    else:
        db = Config.get("Input", "database")
        user = Config.get("Input", "user")
        pw = Config.get("Input", "password")
        host = Config.get("Input", "host")

        conn = psycopg2.connect(database=db, user=user, password=pw, host=host)
    cursor = conn.cursor()

    sql = """SELECT {sql_x}, {sql_y}, {sql_value}
            FROM {sql_table}
            WHERE {sql_x} between %s and %s AND {sql_y} between %s and %s
            """.format(sql_x = Config.get("Sql", "x"),
                       sql_y = Config.get("Sql", "y"),
                       sql_value = Config.get("Sql", "value"),
                       sql_table = Config.get("Sql", "table"))

    resolution = Config.getint("Input", "resolution")

    print "parameters", (min_x, max_x, min_y, max_y)
    cursor.execute(sql, (min_x, max_x, min_y, max_y)) #xmin xmax, ymin, ymax in that order
    #ttes charhra

    records = cursor.fetchall()
    x_vals = zip(*records)[0]
    y_vals = zip(*records)[1]
    count_rows = len(set(y_vals))
    count_cols = len(set(x_vals))
    db_min_x = min(x_vals)
    db_min_y = min(y_vals)

    print (count_rows, count_cols, db_min_x, db_min_y)


    pop_array = np.zeros((count_rows, count_cols), dtype=np.int32)


    a = Affine(
            resolution,
            0,
            db_min_x, #shift from the center marking to bottom left corner
            0,
            -resolution,
            db_min_y + count_rows*resolution #shift from the center marking to bottom left corner
    )

    print "array origins: ", (db_min_x, db_min_y)


    for line in records:
        if line[2] > 0:
            (x,y) = (line[0], line[1])
            #print "(x,y): ", (x,y)
            (col, row) = ~a * (x,y)
            try:
                pop_array[row, col] = line[2]
            except IndexError:
                print "(col,row): ", (col, row), "x,y:", (x,y)

        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print np.sum(pop_array)

    return (pop_array, a)


def load_data(Config, array_origin_x, array_origin_y, size, inverted=False):

    database_string = Config.get("Input", "databaseString")
    if database_string:
        conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
    else:
        db = Config.get("Input", "database")
        user = Config.get("Input", "user")
        pw = Config.get("Input", "password")
        host = Config.get("Input", "host")

        conn = psycopg2.connect(database=db, user=user, password=pw, host=host)
    cursor = conn.cursor()

    sql = """SELECT {sql_x}, {sql_y}, {sql_value}
            FROM {sql_table}
            WHERE {sql_x} between %s and %s AND {sql_y} between %s and %s
            """.format(sql_x = Config.get("Sql", "x"),
                       sql_y = Config.get("Sql", "y"),
                       sql_value = Config.get("Sql", "value"),
                       sql_table = Config.get("Sql", "table"))

    sql_mins = """SELECT min({sql_x}),min({sql_y})
            FROM {sql_table}
            WHERE {sql_x} between %s and %s AND {sql_y} between %s and %s
            """.format(sql_x = Config.get("Sql", "x"),
                       sql_y = Config.get("Sql", "y"),
                       sql_table = Config.get("Sql", "table"))

    resolution = Config.getint("Input", "resolution")


    x_max = array_origin_x + size * resolution
    y_max = array_origin_y + size * resolution

    pop_array = np.zeros((size, size), dtype=np.int32)

    print cursor.mogrify(sql, (array_origin_x, x_max, array_origin_y, y_max))

    cursor.execute(sql_mins, (array_origin_x, x_max, array_origin_y, y_max))
    (results_min_x, results_min_y) = cursor.fetchone()

    a = Affine(
            resolution,
            0,
            results_min_x, #shift from the center marking to bottom left corner
            0,
            -resolution,
            results_min_y + size*resolution #shift from the center marking to bottom left corner
    )

    print "array origins: ", (results_min_x, results_min_y)
    array_origin_x = results_min_x
    array_origin_y = results_min_y
    x_max = results_min_x + size * resolution
    y_max = results_min_y + size * resolution

    #cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
    #this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
    print "parameters", (array_origin_x, (x_max-1), (array_origin_y+1), y_max)
    cursor.execute(sql, (array_origin_x, (x_max-1), (array_origin_y+1), y_max)) #xmin xmax, ymin, ymax in that order
    #ttes charhra


    for line in cursor:
        if line[2] > 0:
            (x,y) = (line[0], line[1])
            #print "(x,y): ", (x,y)
            (col, row) = ~a * (x,y)
            #print "(col,row): ", (col, row)
            pop_array[row, col] = line[2]
        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print np.sum(pop_array)

    return (pop_array, a)


def run_tabulate_intersection(zone_octtree, octtree_crs, land_use_folder, land_use_crs, class_field, field_values):

    #set value for each zones and class to zero
    for zone in zone_octtree.iterate():
        zone.landuse_pc = {}
        zone.landuse_area = {}
        for (field, class_alias) in field_values:
            zone.landuse_pc[class_alias] = 0
            zone.landuse_area[class_alias] = 0

    print "running intersection tabulation"

    print land_use_folder
    for folder in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, folder)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]
            ags = folder[0:3]

            #if int(ags) in [175, 177, 183, 187]: #only for test config

            #print ags, os.path.join(folder_abs, seidlung_path)
            #for each land use shapefile, tabulate intersections for each zone in that shapefile
            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")

            tabulate_intersection(zone_octtree, octtree_crs, full_sp_path, land_use_crs, class_field, field_values)



def tabulate_intersection(zone_octtree, octtreeSaptialRef, shapefile, inSpatialEPSGRef, class_field, field_values):
    #print "running intersection tabulation"
    (land_types, land_type_aliases) = zip(*field_values)
    with fiona.open(shapefile) as src:
        print '\t' , shapefile, '...'

        for feature in src:
            #get class
            poly_class = feature['properties']['OBJART'].lower()
            if poly_class in land_types: #*zip means unzip. Only work with land types we want
                class_alias = land_type_aliases[land_types.index(poly_class)] #make faster?
                #transform
                transform_fiona_polygon(feature, Proj(inSpatialEPSGRef), Proj(octtreeSaptialRef))
                poly = shape(feature['geometry'])

                matches = find_intersections(zone_octtree, poly)

                for zone in matches:
                    #print zone.index, class_name, percentage
                    intersection = zone.polygon.intersection(poly)
                    pc_coverage = min(1, intersection.area / zone.polygon.area) #max 100% area
                    zone.landuse_pc[class_alias] += pc_coverage
                    zone.landuse_area[class_alias] += zone.polygon.area

def find_intersections(node, poly):
    matches = []

    if node.polygon.intersects(poly):
        if isinstance(node, OcttreeLeaf):
            matches.append(node)
        else:
            for child in node.getChildren():
                matches.extend(find_intersections(child, poly))
    return matches

def save(filename, outputSpatialReference, octtree, include_land_use = False, field_values = None):
    print "saving zones with land use to:", filename

    schema = {'geometry': 'Polygon',
                'properties': [('Population', 'int'), ('Area', 'float'), ('AGS', 'int')]}

    if include_land_use:
        for (f, alias) in field_values:
            schema['properties'].append((alias,'float'))
        schema['properties'].append(('remainder', 'float'))

    with fiona.open(
         filename, 'w',
         driver="ESRI Shapefile",
         crs=outputSpatialReference,
         schema=schema) as c:

        for zone in octtree.iterate():

            properties = {'Population': zone.value,
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

def load_program_config():
    return load_config(1, "please supply a configuration file as a program arugment")

def load_config(arg_num, error_message):
    import ConfigParser, sys
    Config = ConfigParser.ConfigParser(allow_no_value=True)

    if len(sys.argv) == 1 or not os.path.exists(sys.argv[arg_num]):
        raise IOError(error_message)
    Config.read(sys.argv[arg_num])
    return Config

def load_land_use_mapping(arg_num):
    Config = load_config(arg_num, "please supply a land use file")
    return [Config.get("Class Values", c) for c in Config.options("Class Values")]

def load_land_use_encodings(arg_num):
    Config = load_config(arg_num, "please supply a land use file")
    return {c : i for (i,c) in enumerate(Config.options("Class Values"))}

def load_scaling_factors(arg_num, key):
    Config = load_config(arg_num, "please supply a land use file")
    try:
        values_strs = Config.get("Scaling Factors", key).split(",")
        values = map(float,values_strs)
        assert np.isclose(sum(values),1.0), "Scaling factors must sum to 1.0"
        return values
    except:
        raise Exception("Please provide valid scaling factors that add to 1.0, ie: '0.2,0.2,0.2,0.2'")
