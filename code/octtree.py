import numpy
import util
from osgeo import ogr
from Queue import Queue
from rasterstats import zonal_stats
import octtree

class Octtree:
    fid_counter = 0

    def __init__(self, polygon):
        self.polygon = polygon    # instance variable unique to each instance


    def iterate(self):
        if isinstance(self, OcttreeLeaf):
            yield self
        else:
            for child in self.getChildren():
                for r in child.iterate():
                    yield r

    def to_geom_wkb_list(self):
        return [n.polygon.ExportToWkb() for n in self.iterate()]

    def find_matches(self, poly, poly_class):

        if self.polygon.Intersects(poly):
            if isinstance(self, OcttreeLeaf):
                intersection = self.polygon.Intersection(poly)
                pc_coverage = intersection.GetArea() / self.polygon.GetArea()
                yield (self, (poly_class, pc_coverage))
            else:
                for child in self.getChildren():
                    for r in child.find_matches(poly, poly_class):
                        yield r

    def find_intersecting_children(self, poly):
        return [child for child in self.getChildren()
                if child.polygon.Intersects(poly) and not child.polygon.Touches(poly)]


    def splice(self, regions, pop_array, transform):
        nodes_to_delete = set()
        for poly in regions:
            node_queue = Queue()
            node_queue.put(self)
            while not node_queue.empty():
                #print node_queue.qsize()
                #for all intersecting nodes, create a new node from the intersection, and mark the old one for deletion
                new_children = [] #dont want to add the children until we have iterated all the old ones (1.)
                top = node_queue.get()
                for child in top.find_intersecting_children(poly):
                    if isinstance(child, OcttreeLeaf):
                        intersection = child.polygon.Intersection(poly)
                        spliced_node = OcttreeLeaf(intersection)
                        spliced_node.parent = child.parent
                        #calculate new population value
                        spliced_node.value = util.calculate_pop_value(spliced_node, pop_array, transform)
                        new_children.append(spliced_node) #see above (1.)
                        nodes_to_delete.add(child)
                    else:
                        node_queue.put(child)
                self.children.extend(new_children)  #see above (1.)
        for node in nodes_to_delete:
            if node in node.parent.getChildren():
                node.parent.remove(node)




class OcttreeLeaf(Octtree):
    def __init__(self, polygon):
        self.polygon = polygon
        self.value = 0

        self.index = Octtree.fid_counter
        Octtree.fid_counter += 1

    def count(self):
        return 1

    def count_populated(self):
        if self.value > 0:
            return 1
        else:
            return 0

    def prune(self, bounding_geo):
        return self.count()

    def to_feature(self, layer):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("fid", self.index)
        feature.SetField("Population", self.value)
        feature.SetGeometry(self.polygon)

        return feature

class OcttreeNode(Octtree):
    def __init__(self, polygon, children, parent = None):
        self.polygon = polygon
        self.children = children
        self.parent = parent

    def getChildren(self):
        return self.children

    def count(self): #get total number of leaves
        counts = map(lambda x: x.count(), self.children)
        return sum(counts)

    def count_populated(self): #get total number of leaves
        counts = map(lambda x: x.count_populated(), self.children)
        return sum(counts)

    def remove(self, child):
        self.children.remove(child)

    def prune(self, bounding_geo):
        self.children = [child for child in self.children if bounding_geo.Intersects(child.polygon)]
        for child in self.children:
            child.prune(bounding_geo)
        return self.count()

def build_out_nodes(region_node, regions, array, affine, pop_threshold):
    octtree.fid_counter = 0

    region_node.children = [build(geom, array, affine, pop_threshold)
                     for geom in regions]
                     #if geom.GetGeometryName() == 'POLYGON']

    for child in region_node.children:
        child.parent = region_node


def build(box, array, affine, pop_threshold): #list of bottom nodes to work from
    #run rasterstats with sum and count

    stats = zonal_stats(box.ExportToWkb(), array, affine=affine, stats="sum count", raster_out=True, nodata=-1)
    if stats[0]['sum'] < pop_threshold or stats[0]['count'] == 1: # leaf #need the count of valid cells
        leaf = OcttreeLeaf(box)
        leaf.value = stats[0]['sum']
        return leaf

    else:  #if np.sum(array) >= pop_threshold and array.size >= 4: # leaf
        #split box into 4
        #recurse to leafs for each subpolygon
        sub_polygons = util.quarter_polygon(box)
        #maybe use clipped and masked sub array
        children = [build(sub, stats[0]['mini_raster_array'], stats[0]['mini_raster_affine'], pop_threshold)
                    for sub in sub_polygons if sub.GetGeometryName() == 'POLYGON'] #type 3 is polygon
        node = OcttreeNode(box, children)
        for child in node.getChildren():
            child.parent = node
        return node


