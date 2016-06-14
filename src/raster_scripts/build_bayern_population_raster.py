import sys, os
import src.util as util
import rasterio
from rasterio.warp import reproject, Resampling
import ConfigParser
from fiona.crs import from_epsg
import pyproj
import numpy as np

Config = util.load_program_config()

#next step, find the 'power of two' box that best captures the polygonal boundary area.
resolution = Config.getint("Input", "resolution")

with rasterio.open("data/temp/region_id_100m.tif") as r_id_f:
    clipping_affine = r_id_f.affine
    crs = pyproj.Proj(r_id_f.crs)
    height = r_id_f.height
    width = r_id_f.width

    xoff = clipping_affine.xoff
    yoff = clipping_affine.yoff
    print "region x,y offsets:", (xoff, yoff)
    to_proj = pyproj.Proj(from_epsg(3035))
    print to_proj
    xx, yy = pyproj.transform(crs, to_proj, xoff, yoff)

    xmax = xx + width*100
    ymin = yy - height*100

    print "pop offsets:", xx, yy, xmax, ymin

(pop_array, affine) = util.load_data2(Config, xx, ymin, xmax, yy)
(height, width) = pop_array.shape

print (height, width)

dest = np.zeros(pop_array.shape, np.int32)

print "reprojecting raster"

reproject(
    pop_array,
    dest,
    src_transform=affine,
    src_crs=from_epsg(3035),
    dst_transform=clipping_affine,
    dst_crs=r_id_f.crs,
    resampling=Resampling.nearest)

print "now saving raster"

with rasterio.open("data/temp/population_zensus_raster.tiff", 'w',
              driver = "GTiff",
              width=width,
              height=height,
              count=1,
              dtype=rasterio.int32,
              crs=r_id_f.crs,
              transform=clipping_affine,
              nodata=0
             ) as output:
    output.write(dest, indexes=1)