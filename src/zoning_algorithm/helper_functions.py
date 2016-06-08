from shapely.geometry import shape, Polygon, LineString
from shapely.ops import cascaded_union
from rasterstats import zonal_stats

def get_region_boundary(regions):
    return cascaded_union([shape(r['geometry']) for r in regions])

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


def calculate_pop_value(node, raster):
    (array,)=raster.read()
    stats = zonal_stats(node.polygon, array, affine=raster.affine, stats="sum", nodata=-1)
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