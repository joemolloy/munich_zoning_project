import numpy
import pprint
from PIL import Image
from osgeo import ogr
from matplotlib import pyplot as plt
from matplotlib import cm

def read_world_file(image_name):
    world_file = open(image_name + '.pgw','r')
    lines = world_file.read().splitlines()
    world_file_parts = {}
    world_file_parts['pixel_size_x'] = float(lines[0])
    world_file_parts['pixel_size_y'] = float(lines[3])
    world_file_parts['x-center_UL'] = float(lines[4])
    world_file_parts['y-center_UL'] = float(lines[5])
    world_file.close()
    return world_file_parts

image_name = 'pop_count_6'
im = Image.open(image_name + '.png')
world_file = read_world_file(image_name)

print im.info
print im.size
print im.format
print im.mode
print im.palette

color_table = [
    255,204,164,64,8,35,0,16
]
color_table_inv = [255-x for x in color_table]

pop_table = [8000,4000,2000,500,250,3,0,0]

imarray = numpy.array(im)
print imarray
print imarray.shape

old_resolution = 5
print imarray.size
num_rows = imarray.shape[0] / old_resolution
num_cols = imarray.shape[1] / old_resolution

#100m x 100m grid.

newimarray = numpy.zeros((num_rows, num_cols), dtype=numpy.int)
pop_array = numpy.zeros((num_rows, num_cols), dtype=numpy.int)

print newimarray.shape
for i in xrange(0, num_rows):
    for j in xrange(0, num_cols):
        old_i = i*old_resolution
        old_j = j*old_resolution
        #print 'start at %d %d' % (i, j)
        im_slice = imarray[old_i:old_i+old_resolution,old_j:old_j+old_resolution]
        counts = numpy.bincount(im_slice.flat)
       # print counts
        newimarray[i,j] = color_table_inv[numpy.argmax(counts)]
        pop_array[i,j] = pop_table[numpy.argmax(counts)]

import zoning_algorithm as za

box = ogr.Geometry(ogr.wkbLinearRing)
xwidth = 198.437896875793850 * 5 * num_cols
ywidth = 198.437896875793850 * 5 * num_rows

#box.AddPoint(world_file['x-center_UL'],world_file['y-center_UL'])
#box.AddPoint(world_file['x-center_UL']+xwidth,world_file['y-center_UL'])
#box.AddPoint(world_file['x-center_UL'],world_file['y-center_UL']+ywidth)
#box.AddPoint(world_file['x-center_UL']+xwidth,world_file['y-center_UL']+ywidth)
#box.AddPoint(world_file['x-center_UL'],world_file['y-center_UL'])

box.AddPoint(0.0, 0.0)
box.AddPoint(0.0, 50.0)
box.AddPoint(50.0, 50.0)
box.AddPoint(50.0, 0.0)
box.AddPoint(0.0, 0.0)


poly = ogr.Geometry(ogr.wkbPolygon)
poly.AddGeometry(box)

octtree = za.run_build_octtree(pop_array, 5000, poly)
pp = pprint.PrettyPrinter(depth=6)
#pp.pprint(octtree)

def build_raster(array):

    from osgeo import gdal
    from osgeo import gdal_array
    from osgeo import osr
    xmin, ymax = (549067.58308810205,5448123.2812010609)

    ncols,nrows = array.size
    xres = 198.437896875793850 * 5
    yres = -198.437896875793850 * 5
    geotransform=(xmin,xres,0,ymax,0, yres)
    # That's (top left x, w-e pixel resolution, rotation (0 if North is up),
    #         top left y, rotation (0 if North is up), n-s pixel resolution)
    # I don't know why rotation is in twice???

    output_raster = gdal.GetDriverByName('GTiff').Create('myraster2.tif',ncols, nrows, 1 ,gdal.GDT_Byte)  # Open the file
    output_raster.SetGeoTransform(geotransform)  # Specify its coordinates
    srs = osr.SpatialReference()                 # Establish its coordinate encoding
    srs.ImportFromEPSG(32632)
                                                 # Anyone know how to specify the
                                                 # IAU2000:49900 Mars encoding?
    output_raster.SetProjection( srs.ExportToWkt() )   # Exports the coordinate system

    band = output_raster.GetRasterBand(1)
    arr = band.ReadAsArray()
    print(arr.shape)  # (656L, 515L)
    print newimarray.shape
                                                       # to the file
    output_raster.GetRasterBand(1).WriteArray(array)   # Writes my array to the raster

    # get bottom left coordinate. and top right. we know points are at 100m intervals.
    # insert points in appropriate spot. (x-left)/100, (y-bottom)/100

    #create raster with ncols and nrows, GDT bigger than byte
    #set geotransform SetGeoTransform((x_min, pixel_size, 0, y_max, 0, -pixel_size))
    #pixel siye = 100?
    #create spatial reference (3035)