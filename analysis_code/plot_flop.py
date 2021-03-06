#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

import sys
if len( sys.argv ) < 2:
	print( "usage: {0} data_file (title)? (yaxis)? (xaxis)?".format( sys.argv[0] ) )
	sys.exit(0)

title = "1762 Rabi Flop" if len(sys.argv) < 3 else sys.argv[2]
yaxis = "Bright Probability" if len(sys.argv) < 4 else sys.argv[3]
xaxis = "1762 Time" if len(sys.argv) < 5 else sys.argv[4]

data = np.genfromtxt( sys.argv[1], delimiter="\t", skip_header=1, dtype=float )

plt.plot( data[:,0], data[:,1] )
plt.title( title )
plt.ylabel( yaxis )
plt.ylim( [0., 1.] )
plt.xlim( 0, 150 )
plt.xlabel( xaxis )

plt.show()
