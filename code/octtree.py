import numpy
import util
from osgeo import ogr
from Queue import Queue
from rasterstats import zonal_stats
import octtree
from collections import defaultdict

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
        return [child for child in self.getChildren() if child.polygon.Intersects(poly)]

    def splice(self, regions, pop_array, transform):
        print "running splice algorithm..."

        to_merge = defaultdict(list)
        region_nodes = defaultdict(list)
        nodes_to_delete = set()
        for region in regions:
            node_queue = Queue()
            node_queue.put(self)
            while not node_queue.empty():

                #print node_queue.qsize()
                #for all intersecting nodes, create a new node from the intersection, and mark the old one for deletion
                top = node_queue.get()
                nodes_inside_region = top.find_intersecting_children(region)

                for child in nodes_inside_region:
                    if isinstance(child, OcttreeLeaf):
                        if child.polygon.Within(region): #inside, so keep and all to list of all nodes
                            region_nodes[region].append(child)
                        else: #on the border, split
                            intersection = child.polygon.Intersection(region) #Check that intersection is a polygon

                            intersections_list = util.get_geom_parts(intersection)

                            for intersection in intersections_list:
                                spliced_node = OcttreeLeaf(intersection, top)
                                region_nodes[region].append(spliced_node)
                                #calculate new population value
                                spliced_node.value = util.calculate_pop_value(spliced_node, pop_array, transform)
                                if spliced_node.value > 50:
                                    top.children.append(spliced_node)
                                else:
                                    #need to combine later
                                    to_merge[region].append(spliced_node)

                                nodes_to_delete.add(child)
                    else:
                        node_queue.put(child)

        for node in nodes_to_delete:
            if node in node.parent.getChildren():
                node.parent.remove(node)

        #need to merge nodes in region that have small area or population size
                #if area or population too small, find neighbouring cells and shared boundaries
        #max_no_nodes = max([len(l) for l in region_node_border_dict.itervalues()])
        #print "max num nodes:", max_no_nodes
        print "running merging"
        for region, node_list in to_merge.iteritems():

            (vert_shared, hori_shared) = util.build_geom_line_dict(region_nodes[region])

            for node in node_list:
                if len(region_nodes[region]) == 1:
                    print "no neighbour needed for: ", node.index
                    node.parent.children.append(node)
                else:
                    best_neighbour = util.find_best_neighbour(node, region_nodes[region], vert_shared, hori_shared)
                    if best_neighbour:
                        best_neighbour.polygon = best_neighbour.polygon.Union(node.polygon)
                        best_neighbour.value = best_neighbour.value + node.value
                        node.parent.remove(node)
                        #need to update our boundary checker
                        region_nodes[region].remove(node)
                        (vert_shared, hori_shared) = util.build_geom_line_dict(region_nodes[region])

                        if best_neighbour not in best_neighbour.parent.children:
                            print "Why wasnt ", best_neighbour.index, "there?"
                            best_neighbour.parent.children.append(best_neighbour)
                    else:
                        print "no neighbour found for: ", node.index, " options were", [n.index for n in region_nodes[region]]






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

    def to_feature(self, layer):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("fid", self.index)
        feature.SetField("Population", self.value)
        feature.SetGeometry(self.polygon)

        return feature

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
        self.children = [child for child in self.children if bounding_geo.Intersects(child.polygon)]
        for child in self.children:
            child.prune(bounding_geo)
        return self.count()

def build_out_nodes(region_node, regions, array, affine, pop_threshold):
    octtree.fid_counter = 0

    octtree_top =  build(region_node.polygon, region_node, array, affine, pop_threshold)

    octtree_top.splice(regions, array, affine)

    return octtree_top


def build(box, parent_node, array, affine, pop_threshold): #list of bottom nodes to work from
    #run rasterstats with sum and count

    stats = zonal_stats(box.ExportToWkb(), array, affine=affine, stats="sum count", raster_out=True, nodata=-1)
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
                    for sub in sub_polygons if sub.GetGeometryName() == 'POLYGON'] #type 3 is polygon
        node.children = children
        return node


