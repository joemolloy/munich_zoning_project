import numpy
from osgeo import ogr
from osgeo import osr
from osgeo import gdal
import os
import math
import itertools

class Octtree:
    counter = 0

    def __init__(self, box):
        self.box = box    # instance variable unique to each instance


    def iterate(self):
        if isinstance(self, OcttreeLeaf):
            yield self
        else:
            for child in self.getChildren():
                for r in child.iterate():
                    yield r


    def find_matches(self, poly, poly_class):

        if self.box.Intersects(poly):
            if isinstance(self, OcttreeLeaf):
                intersection = self.box.Intersection(poly)
                pc_coverage = intersection.GetArea() / self.box.GetArea()
                yield (self, (poly_class, pc_coverage))
            else:
                for child in self.getChildren():
                    for r in child.find_matches(poly, poly_class):
                        yield r

    def add_nodes_to_layer(self, layer):
        for node in self.iterate():
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetField("FID", node.index)
            feature.SetField("Population", node.value)
            feature.SetGeometry(node.box)
            layer.CreateFeature(feature)
            feature.Destroy()


    def save_as_shapefile(self, filename):
        driver = ogr.GetDriverByName("ESRI Shapefile")
        # create the data source
        # Remove output shapefile if it already exists
        if os.path.exists(filename):
            driver.DeleteDataSource(filename)
        data_source = driver.CreateDataSource(filename)

        # create the spatial reference, WGS84
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(3035)

        layer = data_source.CreateLayer("zones", srs, ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("FID", ogr.OFTInteger))
        layer.CreateField(ogr.FieldDefn("Population", ogr.OFTInteger))
        self.add_nodes_to_layer(layer)

        data_source.Destroy()

class OcttreeLeaf(Octtree):
    def __init__(self, array, origin, resolution):
        self.value = numpy.sum(array)
        self.array = array
        self.origin = origin
        self.size = array.shape
        self.resolution = resolution

        self.box = self.to_polygon()

        self.index = Octtree.counter
        Octtree.counter += 1

    def to_polygon(self):
        (origin_left, origin_bottom) = self.origin
        (num_rows, num_cols) = self.size
        resolution = self.resolution
        return coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)

    def count(self):
        return 1

    def count_populated(self):
        if self.value > 0:
            return 1
        else:
            return 0

    def prune(self, bounding_geo):
        return self.count()



    #TODO: this is current pretty slow (mostly fixed by check for 0 values)
    def trim (self, bounding_geo):
        (origin_left, origin_bottom) = self.origin #clean these up

        if self.box.Intersects(bounding_geo) and not self.box.Within(bounding_geo):
            #Trim box
            self.box = self.box.Intersection(bounding_geo)
            #recalculate population
                #convert raster cells to polygons with value
                #adjust value by percentage of coverage by new box
                #sum up values
            value = 0
            it = numpy.nditer(self.array, flags=['multi_index'])
            while not it.finished:
                (y,x) = it.multi_index #'from top, from left'
                if self.array[y,x] > 0: #dont calculate polygons for empty cells
                    poly = coords_to_polygon(origin_left + (x*self.resolution), origin_bottom + (y*self.resolution), 1, 1, self.resolution)
                    original_area = poly.GetArea()
                    new_area = poly.Intersection(bounding_geo).GetArea()
                    #print original_area, new_area, self.array[y,x]
                    value += (new_area / original_area) * self.array[y,x]
                it.iternext()
            self.value = math.ceil(value)


class OcttreeNode(Octtree):
    def __init__(self, box, children):
        self.box = box
        self.children = children

    def getChildren(self):
        return self.children

    def count(self): #get total number of leaves
        counts = map(lambda x: x.count(), self.children)
        return sum(counts)

    def count_populated(self): #get total number of leaves
        counts = map(lambda x: x.count_populated(), self.children)
        return sum(counts)

    def prune(self, bounding_geo):
        self.children[:] = [child for child in self.children if bounding_geo.Intersects(child.box)]
        for child in self.children:
            child.prune(bounding_geo)
        return self.count()

    def trim(self, bounding_geo):
        for child in self.children:
            if not child.box.Within(bounding_geo)and child.box.Intersects(bounding_geo):
                #print 'trim children'
                child.trim(bounding_geo)
            #else:
                #print 'dont trim'



def build(array, origin, resolution, pop_threshold):
    if numpy.sum(array) < pop_threshold or array.size == 1: # leaf
        return OcttreeLeaf(array, origin, resolution)

    else:#if np.sum(array) >= pop_threshold and array.size >= 4: # leaf
        (origin_left, origin_bottom) = origin
        (num_cols, num_rows) = array.shape

        (l,r) = numpy.array_split(array,2, axis=1)
        (lb,lt) = numpy.array_split(l, 2)
        (rb,rt) = numpy.array_split(r, 2)

        #coordinate based origins for sub boxes
        lt_origin =  (origin_left, origin_bottom + lb.shape[1]*resolution)
        lb_origin =  (origin_left, origin_bottom)
        rt_origin =  (origin_left + rb.shape[0]*resolution, origin_bottom + rb.shape[1]*resolution)
        rb_origin =  (origin_left + lb.shape[0]*resolution, origin_bottom)

        box = coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)
        lt = build(lt, lt_origin, resolution, pop_threshold)
        lb = build(lb, lb_origin, resolution, pop_threshold)
        rt = build(rt, rt_origin, resolution, pop_threshold)
        rb = build(rb, rb_origin, resolution, pop_threshold)

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

