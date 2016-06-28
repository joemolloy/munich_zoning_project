from shapely.geometry import shape, Polygon, LineString, mapping
from shapely.ops import cascaded_union
from rasterstats import zonal_stats
import rasterio
import fiona
from pyGr.common.util import check_and_display_results

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

def calculate_pop_value(node, raster_array, affine):
    stats = zonal_stats(node.polygon, raster_array, affine=affine, stats="sum", nodata=-1)
    total = stats[0]['sum']
    if total:
        return total
    else:
        return 0

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

from collections import defaultdict

def validate_zones(region_shapefile, identifier, pop_field, emp_field, zones_shapefile):
    print 'validating zone values against statistics'
    with fiona.open(zones_shapefile) as zs:
        values = defaultdict(list)
        zone_values = [(z['properties']['AGS'],z['properties']['Pop+Emp']) for z in zs]
        for k,v in zone_values:
            values[k].append(v)

    with fiona.open(region_shapefile) as rs:
        results = []
        for r in rs:
            ags = r['properties'][identifier]
            total = r['properties'][pop_field] + r['properties'][emp_field]
            #print ags, total, sum(values[ags]), values[ags]
            results.append((total, sum(values[ags])))

    check_and_display_results(results)


if __name__  == '__main__':
    validate_zones('data/temp2/regions_with_stats', 'AGS_Int', 'pop_2008', 'emp_2008','output/zones')