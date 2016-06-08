from Queue import Queue
from rasterstats import zonal_stats
from shapely.geometry import shape
from helper_functions import *
import numpy as np

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
                    for r in child.find_intersections(poly):
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

def build_out_nodes(Config, region_node, regions, raster, pop_threshold):
    Octtree.fid_counter = 0

    octtree_top =  build(region_node.polygon, region_node, raster, pop_threshold)
    print "\toriginal number zones: ", octtree_top.count_populated()
    splice(Config, octtree_top, regions, raster)

    print "\tafter split and merge: ", octtree_top.count_populated()

    return octtree_top


def build(box, parent_node, raster, pop_threshold): #list of bottom nodes to work from
    #run rasterstats with sum and count
    (x,y,xx,yy) = box.bounds
    #print "bounds", (x,y,xx,yy)
    (col1, row1) = ~raster.affine * (x,y)
    (col2, row2) = ~raster.affine * (xx,yy)
    #print "window", (row2, row1), (col1, col2)

    r_a = raster.read(1, window=((row2, row1), (col1, col2)))
    r_a_sum = np.sum(np.clip(r_a,-1, None))
    #print "thresholds:", pop_threshold, 1, "| count, sum:", r_a.size, r_a_sum

    if r_a_sum < pop_threshold or r_a.size == 1: # leaf #need the count of valid cells
        leaf = OcttreeLeaf(box, parent_node)
        leaf.value = r_a_sum
        if leaf.value == None: leaf.value = 0
        return leaf

    else:  #if np.sum(array) >= pop_threshold and array.size >= 4: # leaf
        #split box into 4
        #recurse to leafs for each subpolygon
        sub_polygons = quarter_polygon(box)
        #maybe use clipped and masked sub array
        node = OcttreeNode(box, None, parent_node)

        children = [build(sub, node, raster, pop_threshold)
                    for sub in sub_polygons if sub.geom_type == 'Polygon'] #type 3 is polygon
        node.children = children
        return node

def splice(Config, tree, regions, raster):
    print "running splice algorithm..."

    region_results = []
    nodes_to_delete = set()

    bounding_area = get_region_boundary(regions) #need to check against boundary too.

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
                    if child.polygon.within(region_poly): #inside, so keep and all to list of all nodes (unles on total boundary)
                        region_results[-1]['all'].add(child)
                        child.region = region
                    else: #on a border, split

                        intersection = child.polygon.intersection(region_poly) #Check that intersection is a polygon

                        intersections_list = get_geom_parts(intersection)

                        for intersection in intersections_list:
                            spliced_node = OcttreeLeaf(intersection, top)
                            spliced_node.region = region
                            region_results[-1]['all'].add(spliced_node)
                            #calculate new population value
                            spliced_node.value = calculate_pop_value(spliced_node, raster)
                            if spliced_node.is_acceptable(Config):
                                top.children.append(spliced_node)
                            else:
                                #need to combine later
                                region_results[-1]['to_merge'].add(spliced_node)

                            nodes_to_delete.add(child)
                else:
                    node_queue.put(child)



    #remove any nodes ouside boundary:
    for node in nodes_to_delete:
        node.parent.remove(node)

    merge(Config, region_results)

    tree.prune(bounding_area)


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
                best_neighbour = find_best_neighbour(node, region_nodes)
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


