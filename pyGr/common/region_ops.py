import fiona
from shapely.geometry import mapping, shape, box
from shapely.ops import cascaded_union

from pyGr.common.util import next_power_of_2

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