import numpy
import util
from Queue import Queue
from rasterstats import zonal_stats
import octtree
from collections import defaultdict
from shapely.geometry import shape

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
        return [n.polygon.wkb for n in self.iterate()]

    def find_intersections(self, poly):

        if self.polygon.intersects(poly):
            if isinstance(self, OcttreeLeaf):
                yield self
            else:
                for child in self.getChildren():
                    for r in child.find_matches(poly):
                        yield r

    def find_intersecting_children(self, poly):
        return [child for child in self.getChildren() if child.polygon.intersects(poly)]

class OcttreeLeaf(Octtree):
    def __init__(self, polygon, parent):
        self.polygon = polygon
        self.value = 0
        self.parent = parent

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

    def is_acceptable(self, Config):
        min_area = Config.getint("Parameters", "minimum_zone_area")
        min_pop = Config.getint("Parameters", "minimum_zone_population")

        return self.value >= min_pop and self.polygon.area >= min_area

    def get_ags(self):
        return self.region['properties']['AGS_Int']

    def get_area(self):
        return self.polygon.area


class OcttreeNode(Octtree):
    def __init__(self, polygon, children, parent):
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
        if child in self.children:
            self.children.remove(child)

    def prune(self, bounding_geo):
        self.children = [child for child in self.children if bounding_geo.intersects(child.polygon)]
        for child in self.children:
            child.prune(bounding_geo)
        return self.count()

def build_out_nodes(Config, region_node, regions, array, affine, pop_threshold):
    octtree.fid_counter = 0

    octtree_top =  build(region_node.polygon, region_node, array, affine, pop_threshold)
    print "\toriginal number zones: ", octtree_top.count_populated()
    splice(Config, octtree_top, regions, array, affine)
    print "\tafter split and merge: ", octtree_top.count_populated()

    return octtree_top


def build(box, parent_node, array, affine, pop_threshold): #list of bottom nodes to work from
    #run rasterstats with sum and count

    stats = zonal_stats(box.wkb, array, affine=affine, stats="sum count", raster_out=True, nodata=-1)
    if stats[0]['sum'] < pop_threshold or stats[0]['count'] == 1: # leaf #need the count of valid cells
        leaf = OcttreeLeaf(box, parent_node)
        leaf.value = stats[0]['sum']
        if leaf.value == None: leaf.value = 0
        return leaf

    else:  #if np.sum(array) >= pop_threshold and array.size >= 4: # leaf
        #split box into 4
        #recurse to leafs for each subpolygon
        sub_polygons = util.quarter_polygon(box)
        #maybe use clipped and masked sub array
        node = OcttreeNode(box, None, parent_node)

        children = [build(sub, node, stats[0]['mini_raster_array'], stats[0]['mini_raster_affine'], pop_threshold)
                    for sub in sub_polygons if sub.geom_type == 'Polygon'] #type 3 is polygon
        node.children = children
        return node

def splice(Config, tree, regions, pop_array, transform):
    print "running splice algorithm..."

    region_results = []
    nodes_to_delete = set()

    boundary = util.get_region_boundary(regions).boundary #need to check against boundary too.

    for region in regions:
        region_results.append({'region':region, 'all':set(), 'to_merge':set()})
        region_poly = shape(region['geometry'])
        node_queue = Queue()
        node_queue.put(tree)
        while not node_queue.empty():

            #print node_queue.qsize()
            #for all intersecting nodes, create a new node from the intersection, and mark the old one for deletion
            top = node_queue.get()
            nodes_inside_region = top.find_intersecting_children(region_poly)

            for child in nodes_inside_region:
                if isinstance(child, OcttreeLeaf):
                    if child.polygon.within(region_poly) and child.polygon.disjoint(boundary): #inside, so keep and all to list of all nodes (unles on total boundary)
                        region_results[-1]['all'].add(child)
                        child.region = region
                    else: #on a border, split

                        intersection = child.polygon.intersection(region_poly) #Check that intersection is a polygon

                        intersections_list = util.get_geom_parts(intersection)

                        for intersection in intersections_list:
                            spliced_node = OcttreeLeaf(intersection, top)
                            spliced_node.region = region
                            region_results[-1]['all'].add(spliced_node)
                            #calculate new population value
                            spliced_node.value = util.calculate_pop_value(spliced_node, pop_array, transform)
                            if spliced_node.is_acceptable(Config):
                                top.children.append(spliced_node)
                            else:
                                #need to combine later
                                region_results[-1]['to_merge'].add(spliced_node)

                            nodes_to_delete.add(child)
                else:
                    node_queue.put(child)

    for node in nodes_to_delete:
        if node in node.parent.getChildren():
            node.parent.remove(node)

    merge(Config, region_results)

def merge(Config, region_results):
    print "running merging"
    for l in region_results:
        merge_set = l['to_merge']
        region_nodes = l['all']
        while len(merge_set):
            node = merge_set.pop()

            if len(region_nodes) == 1:
                #only one in region.
                if node not in node.parent.children:
                    node.parent.children.append(node)
            else:
                best_neighbour = util.find_best_neighbour(node, region_nodes)
                if best_neighbour:
                    best_neighbour.polygon = best_neighbour.polygon.union(node.polygon)
                    best_neighbour.value = best_neighbour.value + node.value

                    node.parent.remove(node)
                    region_nodes.remove(node)

                    if best_neighbour.is_acceptable(Config):
                        if best_neighbour not in best_neighbour.parent.children:
                            best_neighbour.parent.children.append(best_neighbour)
                    else:
                        merge_set.add(best_neighbour)
                else:
                    print "no neighbour found for: ", node.index, " options were", [n.index for n in region_nodes]


