#!script

from bill.models import *

import numpy

B = Bill.objects.filter(congress=113)
C = [b.cosponsors.count() for b in B]
print (sum(C)/float(len(C)), numpy.median(C), sum(1 for c in C if c == 0), len(C))

#


