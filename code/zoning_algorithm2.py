import numpy
from osgeo import ogr
from osgeo import osr
from osgeo import gdal
import os

import octtree

def run_build_octtree(array, origin, resolution, pop_threshold):

    tree = octtree.build(array, origin, resolution, pop_threshold)

    #import matplotlib.pylab as plt
    #plt.imshow(zoned_array.astype(float))
    #plt.show()

    return tree


def iterate_octtree(octtree_node):
    if "value" in octtree_node:
        yield octtree_node
    else:
        for (k, child) in octtree_node.iteritems():
            if k != 'box':
                yield iterate_octtree(child)



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


def add_nodes_to_layer(layer, octtree):
    for node in iterate_octtree(octtree):
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("Population", node["value"])
        feature.SetGeometry(node['box'])
        layer.CreateFeature(feature)
        feature.Destroy()


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
