from octtree import build_out_nodes

import numpy as np
import csv
import time

def model_zones_vs_threshold(Config, region_octtree, regions, raster, raster_affine):
    print 'running trend analysis...'
    results = []
    for pop_threshold in xrange(2000, 20000, 2000):
        octtree = build_out_nodes(Config, region_octtree, regions, raster, raster_affine, pop_threshold, split=False)
        num_zones = octtree.count_populated()
        results.append((pop_threshold, num_zones))
        print results[-1]

    from matplotlib import pyplot

    pyplot.plot(*zip(*results))
    pyplot.xlabel('Data Threshold used (population + employment)')
    pyplot.ylabel('Number of zones created')
    pyplot.title('Trends of zone size')
    pyplot.show()

def solve_iteratively(Config, region_octtree, regions, raster, raster_affine):

    ##
    # if num zones is too large, we need a higher threshold
    # keep a record of the thresholds that result in the nearest low, and nearest high
    # for the next step, take the halfway number between the two

    desired_num_zones = Config.getint("Parameters", "desired_num_zones")
    best_low = Config.getint("Parameters", "lower_population_threshold")
    best_high = Config.getint("Parameters", "upper_population_threshold")
    tolerance =  Config.getfloat("Parameters", "tolerance")

    times = []
    if best_low is None or best_low == 0: best_low = 1
    if best_high is None or best_high == 0: best_high = np.sum(raster)

    step = 1
    solved = False
    num_zones = 0

    pop_threshold = (best_high - best_low) / 2


    start_time = time.time()
    times += [[0, 0]]

    while not solved: # difference greater than 10%
        print 'step %d with threshold level %d...' % (step, pop_threshold)
        prev_num_zones = num_zones
        region_octtree = build_out_nodes(Config, region_octtree, regions, raster, raster_affine, pop_threshold)
        num_zones = region_octtree.count_populated()
        print "\tnumber of cells:", num_zones
        print ''

        solved = prev_num_zones == num_zones or abs(num_zones - desired_num_zones)/float(desired_num_zones) < tolerance
        if not solved:
            if num_zones > desired_num_zones:
                best_low = max (best_low, pop_threshold)
            else:
                best_high = min (best_high, pop_threshold)
            pop_threshold = (best_low + best_high) / 2

        step += 1

        times += [[time.time()-start_time, num_zones]]

    print "Solution found!"
    print "\t%6d zones" % (num_zones)
    print "\t%6d threshold" % (pop_threshold)

    with open('output/time.csv', 'wb') as time_csv:
        fieldnames = ['time', 'zones']
        timewriter = csv.writer(time_csv, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
        timewriter.writerow(fieldnames)
        for x in times:
            timewriter.writerow(x)

    return region_octtree
