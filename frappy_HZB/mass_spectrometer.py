import time


from frappy.datatypes import FloatRange, StringType, StructOf, ArrayOf,StatusType,EnumType
from frappy.lib import clamp, mkthread
from frappy.lib.enum import Enum
from frappy.modules import Command, Drivable, Parameter,Attached,Readable
from frappy.errors import IsErrorError, ReadFailedError, InternalError,   ImpossibleError, IsBusyError
from frappy.core import BUSY, IDLE
import numpy as np
import random
# test custom property (value.test can be changed in config file)


num_spec = 10

Mode = Enum('mode',
    MID_SCAN = 0,
    BAR_SCAN = 1

)    

Device = Enum('device',
    FARADAY = 0,
    SEM = 1
)



class MassSpectrometer(Readable):


    status = Parameter(datatype=StatusType(Readable, 'BUSY'))  
    
    value = Parameter("mass, partial pressure, timestamp",
                      StructOf(
                          mass = ArrayOf(FloatRange(0,1000)),
                          partial_pressure = ArrayOf(FloatRange(0,1000)),
                          timestamp = ArrayOf(FloatRange(0,1000))
                          ))
    
    aquire_time = Parameter("time duration for aquisition of spectrum",
                            FloatRange(0,60),
                            default = 2,
                            unit = "s",
                            readonly = False)
    
    vacuum_pressure = Parameter("Pressure inside the measurement chamber",
                                FloatRange(0,2000),
                                default = 0,
                                unit = "mbar",
                                readonly = True
                                )
    
    mode = Parameter("indicates the current scan mode",
                        EnumType(Mode),
                        readonly = False,
                        default = 1)
    mid_descriptor = Parameter("Datastructure that describes an MID Scan. (massnumber and measurement device for each massnumber)",
                               StructOf(
                                   mass = ArrayOf(FloatRange(0.4,200),1,200),
                                   device = ArrayOf(EnumType(Device),minlen=1,maxlen=200)
                                   ),
                                   readonly = False,
                                   group = 'MID_SCAN',
                                   default = {'mass':[1,2,3],'device':[0,0,0]}
                                )
    
    signal_measurement_device = Parameter("Selects the detector for a bar scan",
                                          EnumType(Device),
                                            group = 'BAR_SCAN',
                                            readonly = False,
                                            default = 0
                                          )
    
    start_mass = Parameter('Start mass number for a bar scan',
                           FloatRange(0.4,200),
                           unit = 'amu',
                           group = 'BAR_SCAN',
                           readonly = False,
                           default = 1)
    
    end_mass = Parameter('End mass number for a bar scan',
                        FloatRange(0.4,200),
                        unit = 'amu',
                        group = 'BAR_SCAN',
                        readonly = False,
                        default = 30)
    
    mass_increment = Parameter('Mass increment between scans in a bar scan',
                               FloatRange(0,200),
                               unit = 'amu',
                               group = 'BAR_SCAN',
                               readonly = False,
                               default = 1)
    
    scan_cycle = Parameter('indicates if in single or continuous cycle mode',
                           EnumType("scan_cycle",{
                               'SINGLE':0,
                               'CONTINUOUS':1
                           }),
                           readonly = False,
                           default = 0)
    
    electron_energy = Parameter('The Electron energy is used to define the filament potential in the Ion Source. This is used to change the Appearance Potential of gasses with similar mass footprints so they can be looked at individually.',
                                FloatRange(0,200),
                                unit = 'V',
                                group = 'global_residual_gas_analysis_parameters',
                                default = 70
                                )
    emission = Parameter('The Emission current is the current which flows from the active filament to the Ion Source Cage. An increase in Emission Current causes an increase in peak intensity, can be used to increase/reduce the peak intensities.',
                         FloatRange(minval=0),
                         unit = 'A',
                         group = 'global_residual_gas_analysis_parameters',
                         default = 250e-06)
    
    focus = Parameter('This is the voltage applied to the Focus plate. This is used to extract the positive Ions from the source and into the Mass Filter, and also to block the transmission of electrons.',
                      FloatRange(minval=-1000,maxval=1000),
                      unit = 'V',
                      group = 'global_residual_gas_analysis_parameters',
                      default = -90)
    
    multiplier = Parameter('The voltage applied to the SEM detector; with a PIC this should be set so the SEM operates in the Plateau Region. With an Analogue system this should be set to 1000 gain, i.e. a scan in Faraday should be equal height using the SEM detector.',
                           FloatRange(minval=0),
                           unit = 'V',
                           group = 'global_residual_gas_analysis_parameters',
                           default = 910)
    
    cage = Parameter('This is the Ion Source Cage voltage which controls the Ion Energy. The higher the Ion Energy the faster the Ions travel through the Mass Filter to the Detector, this reduces the oscillation effect caused by the RF which is applied to the filter.',
                     FloatRange(minval= 0),
                     unit = 'V',
                     group = 'global_residual_gas_analysis_parameters',
                     default = 3)
    
    resolution = Parameter('The high mass peak width/valley adjustment used during set up and maintenance. Can also affect the low masses and should be adjusted in conjunction with the Delta-M.',
                           FloatRange(minval= 0 ),
                           unit = '%',
                           group = 'global_residual_gas_analysis_parameters',
                           default = 0)
    
    delta_m = Parameter('The low mass peak width/valley adjustment used during set up and maintenance. Can also affect the high masses and should be adjusted in conjunction with the Resolution',
                        FloatRange(minval= 0 ),
                        unit = '%',
                        group = 'global_residual_gas_analysis_parameters',
                        default = 0)
    
    start_range = Parameter('Contains the range used at the start of a scan.',
                            FloatRange(minval=0),
                            unit = 'mbar',
                            group = 'acquisition_range',
                            readonly = True,
                            default = 1e-5)
    
    autorange_high = Parameter('The highest range to which the input device may autorange',
                        FloatRange(minval=0),
                        unit = 'mbar',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 1e-5)
    
    autorange_low = Parameter('The lowest range to which the input device may autorange',
                        FloatRange(minval=0),
                        unit = 'mbar',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 1e-10)
    
    settle = Parameter('Defines the time to allow the electronics to settle before the scan is started. Given as a percentage of the default settle time for the current range.',
                        FloatRange(minval=0),
                        unit = '%',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 100)
    
    dwell = Parameter('Defines the time used to acquire a single point in the scan. Given as a percentage of the default settle time for the current range.',
                        FloatRange(minval=0),
                        unit = '%',
                        group = 'acquisition_range',
                        readonly = True,
                        default = 100)
    

    
    



    def initModule(self):
        super().initModule()
        self._stopflag = False
        self._thread = mkthread(self.thread)
        #self.interface_classes = ['Triggerable','Readable']
    

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status
    

    def read_value(self):
        return self.spectrum
    
    def read_vacuum_pressure(self):
        return 1.0e-10 * random.randint(0,1)
    



    @Command()
    def go(self):
        """generate new spectrum"""
        if self.status[0] == BUSY:
            raise IsBusyError('Spectrometer is already scanning')

        self.status = self.Status.BUSY, 'reading Spectrum'
        self.go_flag = True



    def getSpectrum(self):
        start = time.time()
 

        if self.mode == Mode('BAR_SCAN'):
            mass = np.arange(start=self.start_mass,stop=self.end_mass,step=self.mass_increment).tolist()

            num_mass = len(mass)
            partial_pressure = np.random.randint(0,1000,num_mass).tolist()

            timestamps = np.linspace(start=start,stop=start+self.aquire_time,endpoint=False,num=num_mass).tolist()

            return {
                'mass':mass,
                'partial_pressure':partial_pressure,
                'timestamp':timestamps}
            


        elif self.mode == Mode('MID_SCAN'):
            mass = self.mid_descriptor['mass']
            num_mass = len(mass)

            partial_pressure = np.random.randint(0,1000,num_mass).tolist()
            timestamps = np.linspace(start=start,stop=start+self.aquire_time,endpoint=False,num=num_mass).tolist()
            
            return {
                'mass':mass,
                'partial_pressure':partial_pressure,
                'timestamp':timestamps}
        else:
            mass = np.random.randint(0,1000,num_spec).tolist()
            partial_pressure = np.random.randint(0,1000,num_spec).tolist()
            timestamps = np.linspace(start=start,stop=start+self.aquire_time,endpoint=False,num=num_spec).tolist()
            
            return {
                'mass':mass,
                'partial_pressure':partial_pressure,
                'timestamp':timestamps}
        


        
        return new_spectr

    def thread(self):
        self.spectrum = {'mass':[],'partial_pressure':[],'timestamp':[]}
        self.go_flag = False

        self.status = self.Status.IDLE, ''
        while not self._stopflag:
            try:
                self.__sim()
            except Exception as e:
                self.log.exception(e)
                self.status = self.Status.ERROR, str(e)

    def __sim(self):

        # keep history values for stability check
        timestamp = time.time()
        damper = 1

        while not self._stopflag:

            if self.go_flag:
                time.sleep(self.aquire_time)
                self.spectrum = self.getSpectrum()
                self.status = self.Status.IDLE, 'Spectrum finished'
                self.go_flag = False
                self.read_value()

            time.sleep(1)
            self.read_value()

    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()

        

        


        
        