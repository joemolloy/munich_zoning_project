import numpy
import os
import psycopg2
from octtree import OcttreeLeaf, OcttreeNode
import octtree
from rasterstats import zonal_stats
import affine

import fiona
from shapely.geometry import mapping, shape

from pyproj import transform, Proj
from shapely.ops import cascaded_union
from shapely.geometry import LineString, Polygon


def load_regions(shapefile, baseSpatialRef):
    polygons = []

    with fiona.open(shapefile) as src:
        for f in src:
            transform_fiona_polygon(f, Proj(src.crs), Proj(baseSpatialRef))
            g = f['geometry']
            poly = shape(g)
            if poly.geom_type != "Polygon":
                if poly.geom_type in ["MultiPolygon"] :
                    for geom_part in g:
                        polygons.append(geom_part)
            elif poly.geom_type == "Polygon":
                polygons.append(poly)


    return polygons

def transform_fiona_polygon(f, p_in, p_out) :
    new_coords = []
    for ring in f['geometry']['coordinates']:
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

def solve_iteratively(Config, region_octtree, regions, pop_array, affine, boundary):
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
    #TODO: flag to choose whether to include empty zones in counting, and when saving?

    pop_threshold = (best_high - best_low) / 2


    while not solved: # difference greater than 10%
        print 'step %d with threshold level %d...' % (step, pop_threshold)
        region_octtree = octtree.build_out_nodes(Config, region_octtree, regions, pop_array, affine, pop_threshold)
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

    sql = Config.get("Input", "sql")

    resolution = Config.getint("Input", "resolution")


    x_max = array_origin_x + size * resolution
    y_max = array_origin_y + size * resolution

    pop_array = numpy.zeros((size, size), dtype=numpy.int32)

    print cursor.mogrify(sql, (array_origin_x, x_max, array_origin_y, y_max))



    #cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
    #this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
    print "parameters", (array_origin_x, x_max, array_origin_y, y_max)
    cursor.execute(sql, (array_origin_x, x_max, array_origin_y, y_max)) #xmin xmax, ymin, ymax in that order
    #ttes charhra

    a = affine.Affine(100,0,array_origin_x,0,-100,array_origin_y+size*resolution)

    for line in cursor:
        if line[2] > 0:
            (x,y) = (line[0], line[1])
            (col, row) = ~a * (x,y)
            pop_array[row, col] = line[2]
        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print numpy.sum(pop_array)

    return (pop_array, a)
'''
def tabulate_intersection(zone_octtree, octtreeSaptialRef, shapefile, inSpatialEPSGRef, class_field):
    print "running intersection tabulation"
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # load shapefile
    dataSource = driver.Open(shapefile, 0)
    layer = load_layer_from_shapefile(dataSource)

    #get all distinct class_field values
    features = [feature.Clone() for feature in layer]

    field_values = list({f.GetField(class_field)[:8] for f in features})

    #set value for each zones and class to zero
    zones = {node: {} for node in zone_octtree.iterate()}

    for z in zones.iterkeys():
        for c in field_values:
            zones[z][c] = 0

    for feature in features:
        poly_class = feature.GetField(class_field)[:8]
        poly = feature.GetGeometryRef().Clone()

        inSpatialRef = osr.SpatialReference()
        inSpatialRef.ImportFromEPSG(inSpatialEPSGRef) #Germany zone 4 for ALKIS data

        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(octtreeSaptialRef)
        transform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
        poly.Transform(transform)

        matches = zone_octtree.find_matches(poly, poly_class)

        for (zone, (class_name, percentage)) in matches:
            #print zone.index, class_name, percentage
            zones[zone][class_name] += percentage

    return (field_values, zones)
'''
def save(filename, outputSpatialReference, octtree, field_values = None, intersections = None):
    print "saving zones with land use to:", filename

    schema = {'geometry': 'Polygon',
                'properties': [('Population', 'int'), ('Area', 'float')]}

    with fiona.open(
         filename, 'w',
         driver="ESRI Shapefile",
         crs=outputSpatialReference,
         schema=schema) as c:

        if intersections:
            for f in field_values:
                schema['properties'][f] = 'float'

            for zone, classes in intersections.iteritems():
                properties = {'Population' : zone.value, 'Area' : zone.getArea()}
                properties.update(classes)
                c.write({
                    'geometry': zone.polygon,
                    'properties': properties
                })
        else:
            fids = [n.index for n in octtree.iterate()]
            fids.sort()
            for i in range(1, len(fids)):
                if fids[i] == fids[i-1]:
                    print "duplicate fid: ", fids[i]

            #assert(len(set(fids)) == len(fids))

            for zone in octtree.iterate():
                c.write({
                    'geometry': mapping(zone.polygon),
                    'properties': {'Population' : zone.value, 'Area' : zone.polygon.area }
                })




def quarter_polygon(geom_poly):
    #https://pcjericks.github.io/py-gdalogr-cookbook/geometry.html#quarter-polygon-and-create-centroids
    (min_x, min_y, max_x, max_y) = geom_poly.bounds

    '''
    coord0----coord1----coord2
    |           |           |
    coord3----coord4----coord5
    |           |           |
    coord6----coord7----coord8
    '''
    coord0 = min_x, max_y
    coord1 = min_x+(max_x-min_x)/2, max_y
    coord2 = max_x, max_y
    coord3 = min_x, min_y+(max_y-min_y)/2
    coord4 = min_x+(max_x-min_x)/2, min_y+(max_y-min_y)/2
    coord5 = max_x, min_y+(max_y-min_y)/2
    coord6 = min_x, min_y
    coord7 = min_x+(max_x-min_x)/2, min_y
    coord8 = max_x, min_y

    polyTopLeft = Polygon([coord0,coord1,coord4,coord3,coord0])
    polyTopRight = Polygon([coord1,coord2,coord5,coord4,coord1])
    polyBottomLeft = Polygon([coord3,coord4,coord7,coord6,coord3])
    polyBottomRight = Polygon([coord4,coord5,coord8,coord7,coord4])

    quarterPolyTopLeft = polyTopLeft.intersection(geom_poly)
    quarterPolyTopRight =  polyTopRight.intersection(geom_poly)
    quarterPolyBottomLeft =  polyBottomLeft.intersection(geom_poly)
    quarterPolyBottomRight =  polyBottomRight.intersection(geom_poly)

    multipolys = [quarterPolyTopLeft, quarterPolyTopRight, quarterPolyBottomLeft, quarterPolyBottomRight]
    polys = []

    for geom in multipolys:
        if geom.geom_type in ['MultiPolygon', 'GeometryCollection'] :
            for geom_part in geom:
                if geom_part.geom_type == 'Polygon':
                    polys.append(geom_part)
        else:
            polys.append(geom)


    return polys

def get_geom_parts(geom):
    parts = []
    if geom.geom_type in ['MultiPolygon', 'GeometryCollection'] :
        for geom_part in geom:
            if geom_part.geom_type == 'Polygon':
                parts.append(geom_part)
    elif geom.geom_type == 'Polygon': #ignore linestrings and multilinestrings
        parts.append(geom)
    return parts


def calculate_pop_value(node, array, transform):
    stats = zonal_stats(node.polygon, array, affine=transform, stats="sum", nodata=-1)
    total = stats[0]['sum']
    if total:
        return total
    else:
        return 0

def find_best_neighbour(node, neighbours, vert_shared, hori_shared):
    max_length = 0
    best_neighbour = None
    for neighbour in neighbours:
        if node.index != neighbour.index and node.polygon.touches(neighbour.polygon):
            length = get_common_edge_length(node, neighbour, vert_shared, hori_shared)
            if length > max_length:
                max_length = length
                best_neighbour = neighbour
    if max_length == 0:
        print "failed for node:", node.index, "against ", [n.index for n in neighbours]

    return best_neighbour


def get_common_edge_length(node1, node2, geom_vertical_line_parts_map, geom_horizontal_line_parts_map):
    edge_length = 0

    if node1 not in geom_vertical_line_parts_map:
        print "missing node1:", node1.index
    if node2 not in geom_vertical_line_parts_map:
        print "missing node2:", node2.index

    #get all intersecting lines
    vert_shared = [h1.intersection(h2)
                   for h1 in geom_vertical_line_parts_map[node1]
                   for h2 in geom_vertical_line_parts_map[node2]]

    hori_shared = [h1.intersection(h2)
                   for h1 in geom_horizontal_line_parts_map[node1]
                   for h2 in geom_horizontal_line_parts_map[node2]]

    for l in hori_shared+vert_shared:
        if l.geometryType() == "LineString":
            print l.geometryType(), l, l.length
            edge_length = edge_length + l.length

    return edge_length

def get_common_boundary(node1, node2):
    geom1 = node1.polygon
    geom2 = node2.polygon

    lines1 = zip(geom1.exterior.coords[0:-1],geom1.exterior.coords[1:])
    lines2 = zip(geom2.exterior.coords[0:-1],geom2.exterior.coords[1:])

    vert1 = [LineString([(ax,ay),(bx,by)]) for (ax,ay),(bx,by) in lines1 if ax == bx]
    hori1 = [LineString([(ax,ay),(bx,by)]) for (ax,ay),(bx,by) in lines1 if ay == by]

    vert2 = [LineString([(ax,ay),(bx,by)]) for (ax,ay),(bx,by) in lines2 if ax == bx]
    hori2 = [LineString([(ax,ay),(bx,by)]) for (ax,ay),(bx,by) in lines2 if ay == by]

    edge_length = 0

    #get all intersecting lines
    vert_shared = [h1.intersection(h2)
                   for h1 in vert1
                   for h2 in vert2]

    hori_shared = [h1.intersection(h2)
                   for h1 in hori1
                   for h2 in hori2]

    for l in hori_shared+vert_shared:
        if l.geometryType() == "LineString":
            #print l.geometryType(), l, l.length
            edge_length = edge_length + l.length

    return edge_length


def find_best_neighbour(node, neighbours):
    max_length = 0
    best_neighbour = None
    for neighbour in neighbours:
        if node.index != neighbour.index and node.polygon.touches(neighbour.polygon):
            #neighbour_area = neighbour.polygon.GetArea()
            length = get_common_boundary(node, neighbour)
            if length > max_length:
                max_length = length
                best_neighbour = neighbour
    if max_length == 0:
        print "failed for node:", node.index, "against ", [n.index for n in neighbours]

    return best_neighbour
