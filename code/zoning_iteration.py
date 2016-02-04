import zoning_algorithm2 as za

def count_zones(octtree):
    return

def prune_octtree(bounding_geo, octtree_node):
    for (k, child) in octtree_node.items():
            if k != 'box' and bounding_geo.disjoint(child):
                del octtree_node[k]
