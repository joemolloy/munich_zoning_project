
import math

def roundup_to_multiple_of(x, v):
     return x if x % v == 0 else x + v - x % v

#Round up to next higher power of 2 (return x if it's already a power of 2).
#from http://stackoverflow.com/questions/1322510
def next_power_of_2(n):
    """
    Return next power of 2 greater than or equal to n
    """
    return 2**(n-1).bit_length()

def check_and_display_results(results):
    actuals, calcd = zip(*results)
    print "\t actual:", "{:,}".format(sum(actuals))
    print "\t calculated:", "{:,}".format(sum(calcd))
    print "\t difference:", "{:,}".format(sum(actuals) - sum(calcd))

    print "\t RMSE:", "{:,}".format(math.sqrt(sum([(a-b)**2 for (a,b) in results]) / len(results)))
