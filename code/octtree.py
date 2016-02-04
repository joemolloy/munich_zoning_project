import numpy
from osgeo import ogr
from osgeo import osr
from osgeo import gdal

class Octtree:
    def __init__(self, box):
        self.box = box    # instance variable unique to each instance


class OcttreeLeaf(Octtree):
    def __init__(self, array, origin, resolution):
        self.value = numpy.sum(array)
        self.origin = origin
        self.size = array.shape
        self.resolution = resolution

        self.box = self.to_polygon()

    def to_polygon(self):
        (origin_left, origin_bottom) = self.origin
        (num_rows, num_cols) = self.size
        resolution = self.resolution
        return coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)

class OcttreeNode(Octtree):
    def __init__(self, box, children):
        self.box = box
        self.children = children


def build(array, origin, resolution, pop_threshold):
    if numpy.sum(array) < pop_threshold or array.size == 1: # leaf
        return OcttreeLeaf(array, origin, resolution)

    else:#if np.sum(array) >= pop_threshold and array.size >= 4: # leaf
        (origin_left, origin_bottom) = origin
        (num_cols, num_rows) = array.shape

        (l,r) = numpy.array_split(array,2, axis=1)
        (lt,lb) = numpy.array_split(l, 2)
        (rt,rb) = numpy.array_split(r, 2)

        #coordinate based origins for sub boxes
        lt_origin =  (origin_left, origin_bottom + lb.shape[1]*resolution)
        lb_origin =  (origin_left, origin_bottom)
        rt_origin =  (origin_left + rb.shape[0]*resolution, origin_bottom + rb.shape[1]*resolution)
        rb_origin =  (origin_left + lb.shape[0]*resolution, origin_bottom)

        box = coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)
        lt = build_octtree(lt, lt_origin, resolution, pop_threshold)
        lb = build_octtree(lb, lb_origin, resolution, pop_threshold)
        rt = build_octtree(rt, rt_origin, resolution, pop_threshold)
        rb = build_octtree(rb, rb_origin, resolution, pop_threshold)

        return OcttreeNode(box, [lt,lb,rt,rb])

def coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution):
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint_2D(origin_left, origin_bottom)
    ring.AddPoint_2D(origin_left, origin_bottom+num_cols*resolution)
    ring.AddPoint_2D(origin_left+num_rows*resolution, origin_bottom+num_cols*resolution)
    ring.AddPoint_2D(origin_left+num_rows*resolution, origin_bottom)
    ring.AddPoint_2D(origin_left, origin_bottom)
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    return poly