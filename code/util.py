import numpy
import os
from osgeo import ogr, osr
import psycopg2
import octtree
from rasterstats import zonal_stats
import affine

def load_regions(shapefile, baseSpatialRef):
    polygons = []
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # load shapefile
    dataSource = driver.Open(shapefile, 0)

    layer = load_layer_from_shapefile(dataSource)
    for feature in layer:
        geom = feature.GetGeometryRef().Clone()

        #convert to EPSG:3035
        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(baseSpatialRef)
        geom.TransformTo(outSpatialRef)

        polygons.append(geom)

    return polygons

def load_layer_from_shapefile(dataSource):

    if dataSource is None:
        print 'Could not open %s' % (dataSource.GetName())
        return None
    else:
        print 'Opened %s' % (dataSource.GetName())
        layer = dataSource.GetLayer()

        featureCount = layer.GetFeatureCount()
        fieldCount = layer.GetLayerDefn().GetFieldCount()
        print "Number of features: %d, Number of fields: %d" % (featureCount, fieldCount)
        return layer


#Round up to next higher power of 2 (return x if it's already a power of 2).
#from http://stackoverflow.com/questions/1322510
def next_power_of_2(n):
    """
    Return next power of 2 greater than or equal to n
    """
    return 2**(n-1).bit_length()

def solve_iteratively(Config, box, pop_array, affine, boundary):
    ##
    # if num zones is too large, we need a higher threshold
    # keep a record of the thresholds that result in the nearest low, and nearest high
    # for the next step, take the halfway number between the two

    desired_num_zones = Config.getint("Parameters", "population_threshold")
    best_low = Config.getint("Parameters", "lower_population_threshold")
    best_high = Config.getint("Parameters", "upper_population_threshold")
    tolerance =  Config.getfloat("Parameters", "tolerance")

    step = 1
    solved = False
    num_zones = 0
    #TODO: flag to choose whether to include empty zones in counting, and when saving?

    pop_threshold = (best_high - best_low) / 2


    while not solved: # difference greater than 10%
        result_octtree = octtree.build(box, pop_array, affine, pop_threshold)
        print 'step %d with threshold level %d' % (step, pop_threshold)
        print "\toriginal number of cells:", result_octtree.count()
        num_zones = result_octtree.prune(boundary)
        print "\tafter pruning to boundary:", num_zones
        print ''

        solved = abs(num_zones - desired_num_zones)/float(desired_num_zones) < tolerance
        if not solved:
            if num_zones > desired_num_zones:
                best_low = max (best_low, pop_threshold)
            else:
                best_high = min (best_high, pop_threshold)
            pop_threshold = (best_low + best_high) / 2

        step += 1

    print "Solution found!"
    print "\t%6d zones" % (num_zones)
    print "\t%6d threshold" % (pop_threshold)

    return result_octtree



def load_data(Config, array_origin_x, array_origin_y, size, inverted=False):

    database_string = Config.get("Input", "databaseString")
    if database_string:
        conn = psycopg2.connect(None, "arcgis", "postgres", "postgres")
    else:
        db = Config.get("Input", "database")
        user = Config.get("Input", "user")
        pw = Config.get("Input", "password")
        host = Config.get("Input", "host")

        conn = psycopg2.connect(database=db, user=user, password=pw, host=host)
    cursor = conn.cursor()

    sql = Config.get("Input", "sql")

    resolution = Config.getint("Input", "resolution")

    x_max = array_origin_x + size * resolution
    y_max = array_origin_y + size * resolution

    pop_array = numpy.zeros((size, size), dtype=numpy.int32)

    #cursor.execute("SELECT x_mp_100m, y_mp_100m, \"Einwohner\" FROM public.muc_all_population;")
    #this metheod only works when total rows = ncols x nrows in database. (IE no missing values)
    print "parameters", (array_origin_x, x_max, array_origin_y, y_max)
    cursor.execute(sql, (array_origin_x, x_max, array_origin_y, y_max)) #xmin xmax, ymin, ymax in that order
    #ttes charhra

    a = affine.Affine(100,0,array_origin_x,0,-100,array_origin_y+size*resolution)

    for line in cursor:
        if line[2] > 0:
            (x,y) = (line[0], line[1])
            (col, row) = ~a * (x,y)
            pop_array[row, col] = line[2]
        #reference arrays by (row_no , col_no)
        #reference arrays by (   a_y,      a_x   )

    print numpy.sum(pop_array)

    return (pop_array, a)

def tabulate_intersection(zone_octtree, octtreeSaptialRef, shapefile, inSpatialEPSGRef, class_field):
    print "running intersection tabulation"
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # load shapefile
    dataSource = driver.Open(shapefile, 0)
    layer = load_layer_from_shapefile(dataSource)

    #get all distinct class_field values
    features = [feature.Clone() for feature in layer]

    field_values = list({f.GetField(class_field)[:8] for f in features})

    #set value for each zones and class to zero
    zones = {node: {} for node in zone_octtree.iterate()}

    for z in zones.iterkeys():
        for c in field_values:
            zones[z][c] = 0

    for feature in features:
        poly_class = feature.GetField(class_field)[:8]
        poly = feature.GetGeometryRef().Clone()

        inSpatialRef = osr.SpatialReference()
        inSpatialRef.ImportFromEPSG(inSpatialEPSGRef) #Germany zone 4 for ALKIS data

        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(octtreeSaptialRef)
        transform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
        poly.Transform(transform)

        matches = zone_octtree.find_matches(poly, poly_class)

        for (zone, (class_name, percentage)) in matches:
            #print zone.index, class_name, percentage
            zones[zone][class_name] += percentage

    return (field_values, zones)

def save(filename, outputSpatialReference, field_values = None, intersections = None):
    print "saving zones to:", filename
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # create the data source
    if os.path.exists(filename):
        driver.DeleteDataSource(filename)
    data_source = driver.CreateDataSource(filename)

    outputSRS = osr.SpatialReference()
    outputSRS.ImportFromEPSG(outputSpatialReference)

    layer = data_source.CreateLayer("zones", outputSRS, ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("fid", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("Population", ogr.OFTInteger))

    if field_values and intersections:
        for f in field_values:
            layer.CreateField(ogr.FieldDefn(f, ogr.OFTReal))

        for zone, classes in intersections.iteritems():
            feature = zone.to_feature(layer)
            for c, percentage in classes.iteritems():
                feature.SetField(c, percentage)
            if feature.GetGeometryRef().GetGeometryType() == 3: #is a polygon
                layer.CreateFeature(feature)

            feature.Destroy()


    data_source.Destroy()

#split along region borders
#recalculate

def quarter_polygon(geom_poly):
    #https://pcjericks.github.io/py-gdalogr-cookbook/geometry.html#quarter-polygon-and-create-centroids
    geom_poly_envelope = geom_poly.GetEnvelope()
    minX = geom_poly_envelope[0]
    minY = geom_poly_envelope[2]
    maxX = geom_poly_envelope[1]
    maxY = geom_poly_envelope[3]

    '''
    coord0----coord1----coord2
    |           |           |
    coord3----coord4----coord5
    |           |           |
    coord6----coord7----coord8
    '''
    coord0 = minX, maxY
    coord1 = minX+(maxX-minX)/2, maxY
    coord2 = maxX, maxY
    coord3 = minX, minY+(maxY-minY)/2
    coord4 = minX+(maxX-minX)/2, minY+(maxY-minY)/2
    coord5 = maxX, minY+(maxY-minY)/2
    coord6 = minX, minY
    coord7 = minX+(maxX-minX)/2, minY
    coord8 = maxX, minY

    ringTopLeft = ogr.Geometry(ogr.wkbLinearRing)
    ringTopLeft.AddPoint_2D(*coord0)
    ringTopLeft.AddPoint_2D(*coord1)
    ringTopLeft.AddPoint_2D(*coord4)
    ringTopLeft.AddPoint_2D(*coord3)
    ringTopLeft.AddPoint_2D(*coord0)
    polyTopLeft = ogr.Geometry(ogr.wkbPolygon)
    polyTopLeft.AddGeometry(ringTopLeft)


    ringTopRight = ogr.Geometry(ogr.wkbLinearRing)
    ringTopRight.AddPoint_2D(*coord1)
    ringTopRight.AddPoint_2D(*coord2)
    ringTopRight.AddPoint_2D(*coord5)
    ringTopRight.AddPoint_2D(*coord4)
    ringTopRight.AddPoint_2D(*coord1)
    polyTopRight = ogr.Geometry(ogr.wkbPolygon)
    polyTopRight.AddGeometry(ringTopRight)


    ringBottomLeft = ogr.Geometry(ogr.wkbLinearRing)
    ringBottomLeft.AddPoint_2D(*coord3)
    ringBottomLeft.AddPoint_2D(*coord4)
    ringBottomLeft.AddPoint_2D(*coord7)
    ringBottomLeft.AddPoint_2D(*coord6)
    ringBottomLeft.AddPoint_2D(*coord3)
    polyBottomLeft = ogr.Geometry(ogr.wkbPolygon)
    polyBottomLeft.AddGeometry(ringBottomLeft)


    ringBottomRight = ogr.Geometry(ogr.wkbLinearRing)
    ringBottomRight.AddPoint_2D(*coord4)
    ringBottomRight.AddPoint_2D(*coord5)
    ringBottomRight.AddPoint_2D(*coord8)
    ringBottomRight.AddPoint_2D(*coord7)
    ringBottomRight.AddPoint_2D(*coord4)
    polyBottomRight = ogr.Geometry(ogr.wkbPolygon)
    polyBottomRight.AddGeometry(ringBottomRight)

    return [polyTopLeft, polyTopRight, polyBottomLeft, polyBottomRight]

def calculate_pop_value(node, array, transform):
    stats = zonal_stats(node.polygon.ExportToWkb(), array, affine=transform, stats="sum", nodata=-1)
    return stats[0]['sum']

def merge_polygons(polygons):
    unionc = ogr.Geometry(ogr.wkbMultiPolygon)
    for p in polygons:
        unionc.AddGeometry(p)
    union = unionc.UnionCascaded()
    return union