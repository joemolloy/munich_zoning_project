import numpy
from osgeo import ogr
from osgeo import osr
from osgeo import gdal
import os

def run_build_octtree(array, origin, resolution, pop_threshold):

    zoned_array = numpy.zeros(numpy.shape(array), dtype=numpy.int)

    (nrows,ncols) = numpy.shape(array)

    tree = build_octtree(array, origin, ((nrows-1), 0), resolution, pop_threshold, zoned_array)

    #import matplotlib.pylab as plt
    #plt.imshow(zoned_array.astype(float))
    #plt.show()

    return (tree, zoned_array)

def build_octtree(array, origin, array_origins, resolution, pop_threshold, zoned_array):

    (origin_left, origin_bottom) = origin
    (num_cols, num_rows) = array.shape
    (array_y,array_x) = array_origins
    octnode_dict = {}

    if numpy.sum(array) < pop_threshold or array.size == 1: # leaf
        octnode_dict['value'] = numpy.sum(array)
        octnode_dict['origin'] = origin
        octnode_dict['size'] = array.shape
        octnode_dict['resolution'] = resolution
        octnode_dict['box'] = node_to_polygon(octnode_dict)

        for i in range(0,num_cols):
            for j in range(0,num_rows):
                zoned_array[array_y-j,array_x+i] = numpy.sum(array)

    else:#if np.sum(array) >= pop_threshold and array.size >= 4: # leaf

        (l,r) = numpy.array_split(array,2, axis=1)
        (lt,lb) = numpy.array_split(l, 2)
        (rt,rb) = numpy.array_split(r, 2)

        #coordinate based origins for sub boxes
        lt_origin =  (origin_left, origin_bottom + lb.shape[1]*resolution)
        lb_origin =  (origin_left, origin_bottom)
        rt_origin =  (origin_left + rb.shape[0]*resolution, origin_bottom + rb.shape[1]*resolution)
        rb_origin =  (origin_left + lb.shape[0]*resolution, origin_bottom)

        #array reference origins for split arrays
        rb_a_origin =  (array_y, array_x + rb.shape[1])
        lb_a_origin =  (array_y, array_x)
        rt_a_origin =  (array_y - rb.shape[0], array_x + rb.shape[1])
        lt_a_origin =  (array_y - lb.shape[0], array_x)

        octnode_dict['box'] = coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)
        octnode_dict['lt'] = build_octtree(lt, lt_origin, lt_a_origin, resolution, pop_threshold, zoned_array)
        octnode_dict['lb'] = build_octtree(lb, lb_origin, lb_a_origin, resolution, pop_threshold, zoned_array)
        octnode_dict['rt'] = build_octtree(rt, rt_origin, rt_a_origin, resolution, pop_threshold, zoned_array)
        octnode_dict['rb'] = build_octtree(rb, rb_origin, rb_a_origin, resolution, pop_threshold, zoned_array)


    return octnode_dict

def iterate_octtree(octtree_node):
    if "value" in octtree_node:
        yield octtree_node
    else:
        for (k, child) in octtree_node.iteritems():
            if k != 'box':
                yield iterate_octtree(child)

def node_to_polygon(node):
    (origin_left, origin_bottom) = node["origin"]
    (num_rows, num_cols) = node["size"]
    resolution = node["resolution"]
    return coords_to_polygon(origin_left, origin_bottom, num_cols, num_rows, resolution)

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

def create_shapefile(octtree):
    driver = ogr.GetDriverByName("ESRI Shapefile")
    # create the data source
    # Remove output shapefile if it already exists
    if os.path.exists("zones"):
        driver.DeleteDataSource("zones")
    data_source = driver.CreateDataSource("zones")

    # create the spatial reference, WGS84
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3035)

    layer = data_source.CreateLayer("zones", srs, ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("Population", ogr.OFTInteger))
    add_nodes_to_layer(layer, octtree)

    data_source.Destroy()


def add_nodes_to_layer(layer, octtree_node):

    if "value" in octtree_node:

        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("Population", octtree_node["value"])
        feature.SetGeometry(octtree_node['box'])
        layer.CreateFeature(feature)
        feature.Destroy()
    else:
        for (k, child) in octtree_node.iteritems():
            if k != 'box':
                add_nodes_to_layer(layer, child)

def export_to_raster(array, xmin, ymax, ncols, nrows, resolution, filename):
    geotransform=(xmin,resolution,0,ymax,0, -resolution)
    # That's (top left x, w-e pixel resolution, rotation (0 if North is up),
    #         top left y, rotation (0 if North is up), n-s pixel resolution)
    # I don't know why rotation is in twice???

    output_raster = gdal.GetDriverByName('GTiff').Create('popraster.tif',ncols, nrows, 1 ,gdal.GDT_Int32)  # Open the file
    output_raster.SetGeoTransform(geotransform)  # Specify its coordinates
    srs = osr.SpatialReference()                 # Establish its coordinate encoding
    srs.ImportFromEPSG(3035)                     # This one specifies WGS84 lat long.
                                                 # Anyone know how to specify the
                                                 # IAU2000:49900 Mars encoding?
    output_raster.SetProjection( srs.ExportToWkt() )   # Exports the coordinate system
                                                       # to the file
    output_raster.GetRasterBand(1).WriteArray(array)   # Writes my array to the raster
