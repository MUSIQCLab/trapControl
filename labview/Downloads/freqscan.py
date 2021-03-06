
import time

from luca import Luca
from freq import FreqDriver
from ni_digital_io import NiDriver
from ni_simple_digital_io import NiDriver as NiSimpleDriver
import numpy as np

#Assume at creation that pause!=False
pause=False;

class ExperimentBase:
    Pockels = 1 << 2
    Red = 1 << 7
    Blue = 1 << 6
    Orange = 1 << 5
    Shelve = 1 << 1
    def build_waveform( self, dark_time, shelve_time ):
        waveform = [self.Pockels | self.Red | self.Blue] * 2000
        waveform.extend( [self.Pockels | self.Red] * 10 )
        waveform.extend( [self.Pockels] * 10 )

        waveform.extend( [self.Orange] * dark_time )
        waveform.extend( [0] * 10 )

        waveform.extend( [self.Shelve] * shelve_time )
        waveform.extend( [0] * 10 )
        waveform.extend( [self.Red | self.Blue] * 10 )
        return waveform

class RabiFlop( ExperimentBase ):
    def __init__( self, start_time, stop_time, time_step, frequency ):
        self.current_time = start_time
        self.stop_time = stop_time
        self.time_step = time_step
        self.frequency = frequency
        
    def setup( self, freq_driver, ni_driver ):
        self.freq_driver = freq_driver
        self.ni_driver = ni_driver
        self.freq_driver.set_frequency( self.frequency, 2.5 )

    def step( self, freq_driver, ni_driver ):
        if self.current_time > self.stop_time:
            return False
        self.ni_driver.set_samples( self.build_waveform( 0, self.current_time ) )
        self.current_time += self.time_step
        return True

    def control_var( self ):
        return self.current_time - self.time_step

class FreqScan( ExperimentBase ):
    def __init__( self, start_freq, stop_freq, freq_step, pulse_duration ):
        self.current_freq = start_freq
        self.stop_freq = stop_freq
        self.freq_step = freq_step
        self.pulse_duration = pulse_duration

    def setup( self, freq_driver, ni_driver ):
        self.freq_driver = freq_driver
        self.ni_driver = ni_driver
        self.ni_driver.set_samples( self.build_waveform( 0, self.pulse_duration ) )

    def step( self, freq_driver, ni_driver ):
        if self.current_freq > self.stop_freq:
            return False
        self.freq_driver.set_frequency( self.current_freq, 2.5 )
        self.current_freq += self.freq_step
        return True

    def control_var( self ):
        return self.current_freq - self.freq_step

def togglePause():
    #Change pause value
    global pause
    pause=not pause
    return

class Experiment:
    PockelsChan = "PXI1Slot9/port0/line2"
    RedChan = "PXI1Slot9/port0/line7"
    BlueChan = "PXI1Slot9/port0/line6"
    OrangeChan = "PXI1Slot9/port0/line5"
    ShelveChan = "PXI1Slot9/port0/line1"
    Chans = ",".join( [PockelsChan, RedChan, 
        BlueChan, OrangeChan, ShelveChan] )
   
    def __init__( self, nruns, experiment, ions, desired_order, out, conn=None ):
        #0 = no sym, use order 1 = symmetrize on order 2 = no order specificity
        camera = Luca()
        freq_src = FreqDriver( u'USB0::0x1AB1::0x0641::DG4B142100247::INSTR' )
        ni = NiDriver( self.Chans )
        reorder_time = 0.5

        output = open( out, 'w' )
        ion_order = []
        desired_bright_number = sum(map(lambda x: 1 if x else 0, desired_order))

        try:
            ion_positions = []
            with open( ions, 'r' ) as ionfile:
                for l in ionfile:
                    pos = tuple( int(x) for x in l.split() )
                    ion_positions.append( pos )
    
            bg = []
            for i in range(30):
                data = self.build_data(camera, ion_positions, camera.get_image())
                bg.append( data[-1] )
            threshold = np.mean(bg) + 3*np.std(bg)
            
            experiment.setup( freq_src, ni )
            print( ion_positions )
            while experiment.step( freq_src, ni ):
                for i in range( nruns ):
                    data = self.build_data(
                        camera, ion_positions, camera.get_image() )
                    ion_order = [ d > threshold for d in data ]

                    bg.append( data[-1] )
                    if len( bg ) > 1000:
                        bg = bg[100:]
                    threshold = np.mean(bg) + 3*np.std(bg)

                    while ion_order != desired_order:
                        #If the code 'switch' is received in the Pipe, switch the value of pause
                        if(conn is not None and conn.recv()=="switch"):
                            global pause
                            pause=not pause
                        if not pause:
                            #Only run the following if the GUI is currently not paused
                            curr_bright_number = sum(map(lambda x: 1 if x else 0, ion_order))
                            if curr_bright_number == desired_bright_number:

                                r = NiSimpleDriver( self.RedChan )
                                r.write_single( False )
                                time.sleep( reorder_time )
                                r.write_single( True )
                                r.close()
                            time.sleep( 0.5 )

                            camera.get_image()
                            data = self.build_data(
                                camera, ion_positions, camera.get_image() )

                            prev_order, ion_order = ion_order, \
                                [ d > threshold for d in data ]
                            print( "{} -> {}".format( prev_order, ion_order ) )

                            if any( prev_order ):
                                if prev_order == ion_order:
                                    reorder_time *= 1.1
                                else:
                                    reorder_time *= 0.9
                                print( "New reorder time: {}".format( reorder_time ) )
                            if reorder_time < 0.1:  reorder_time = 0.1
                            if reorder_time > 10.0: reorder_time = 10.0

                            if conn is not None:
                                outdata = [str( experiment.control_var() )]
                                outdata.extend( str(d) for d in data )
                                outdata.extend( str(d) for d in data )
                                #check
                                conn.send( 'reordata ' + '\t'.join(outdata) )


                    ni.run()
                    data.extend( self.build_data(
                        camera, ion_positions, camera.get_image() ) )

                    outdata = [str( experiment.control_var() )]
                    outdata.extend( str(d) for d in data )
                    print '\t'.join(outdata)
                    if conn is not None:
                        conn.send('\t'.join(outdata) )
                    output.write( '\t'.join(outdata) + '\n' )
                    output.flush()

                    d = NiSimpleDriver( self.OrangeChan )
                    d.write_single( True )
                    d.close()

                    time.sleep( 0.2 )
              
              
        finally:
            camera.shutdown()

    #check floodfill, region count.  ionpos represents an array of x and y points.
    def build_data( self, camera, ionpos, image ):
        data = []
        sum_dist = 20
        for p in ionpos:
            val = 0
            for ox in range( -sum_dist, sum_dist ):
                for oy in range( -sum_dist, sum_dist ):
                    val += image[ (p[1] + oy) * camera.width + p[0] + ox ]
            data.append( val )
        return data

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 4:
        print "usage: {0} <nruns> <high freq (MHz)> <low freq (MHz)> \
            <freq step(MHz)> <1762 pulse length (us)> <ion_positions> \
            <output>".format( sys.argv[0] )
        sys.exit( 0 )
    nruns = int( sys.argv[1] )
    current_freq = float( sys.argv[2] )
    stop_freq = float( sys.argv[3] )
    freq_step = float( sys.argv[4] )
    pulse_len = int( sys.argv[5] )
    ions = sys.argv[6]
    output = sys.argv[7]

    Experiment( nruns, current_freq, stop_freq, freq_step, pulse_len,
        ions, output, None )

