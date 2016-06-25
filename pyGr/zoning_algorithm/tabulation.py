import os
import fiona
from shapely.geometry import shape
def run_tabulate_intersection(zone_octtree, land_use_folder, class_field, field_values):
    print field_values

    #set value for each zones and class to zero
    for zone in zone_octtree.iterate():
        zone.landuse_pc = {}
        zone.landuse_area = {}
        for (field, class_alias) in field_values:
            zone.landuse_pc[class_alias] = 0
            zone.landuse_area[class_alias] = 0

    print "running intersection tabulation"

    print land_use_folder
    checked_features = set() #need to make sure that we dont double count features that are in two files (rely on unique OIDs)

    for folder in os.listdir(land_use_folder):
        folder_abs = os.path.join(land_use_folder, folder)
        if os.path.isdir(folder_abs):
            #find siedlung shapefile name
            seidlung_path = [os.path.splitext(filename)[0]
                             for filename in os.listdir(folder_abs) if 'Siedlung' in filename][0]

            full_sp_path = os.path.join(folder_abs, seidlung_path + ".shp")
            tabulate_intersection(zone_octtree, full_sp_path, checked_features, class_field, field_values)

def tabulate_intersection(zone_octtree, shapefile, checked_features, class_field, field_values):
    #print "running intersection tabulation"
    (land_types, land_type_aliases) = zip(*field_values)
    with fiona.open(shapefile) as src:
        print '\t' , shapefile, '...'

        for feature in src:
            oid = feature['properties']['OID']
            if oid not in checked_features:
                checked_features.add(oid)
                #need to check the OID. If it has already been checked in another land use file, ignore.
                #get class
                poly_class = feature['properties'][class_field].lower()
                if poly_class in land_types: #*zip means unzip. Only work with land types we want
                    class_alias = land_type_aliases[land_types.index(poly_class)] #make faster?
                    #transform
                    poly = shape(feature['geometry'])

                    matches = find_intersections(zone_octtree, poly)

                    for zone in matches:
                        #print zone.index, class_name, percentage
                        intersection = zone.polygon.intersection(poly)
                        pc_coverage = intersection.area / zone.polygon.area
                        zone.landuse_pc[class_alias] += pc_coverage
                        zone.landuse_area[class_alias] += intersection.area

def find_intersections(node, poly):
    matches = []

    if node.polygon.intersects(poly):
        try:
            for child in node.getChildren():
                matches.extend(find_intersections(child, poly))
        except AttributeError: #octtreeleaf
            matches.append(node)

    return matches

