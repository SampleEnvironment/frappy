import time


from frappy.datatypes import FloatRange, StringType, StructOf, ArrayOf,StatusType
from frappy.lib import clamp, mkthread
from frappy.modules import Command, Drivable, Parameter,Attached,Readable
import numpy as np
# test custom property (value.test can be changed in config file)


num_spec = 10

class MassSpectrometer(Readable):

    status = Parameter(datatype=StatusType(Readable, 'BUSY'))  
    
    value = Parameter("mass, partial pressure, timestamp",
                      StructOf(
                          mass = ArrayOf(FloatRange(0,1000),num_spec,num_spec),
                          partial_pressure = ArrayOf(FloatRange(0,1000),num_spec,num_spec),
                          timestamp = ArrayOf(FloatRange(0,1000),num_spec,num_spec)
                          ))
    
    aquire_time = Parameter("time duration for aquisition of spectrum",
                            FloatRange(0,60),
                            default = 2,
                            unit = "s",
                            readonly = False)
    
    def initModule(self):
        super().initModule()
        self._stopflag = False
        self._thread = mkthread(self.thread)
    

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status
    
    def read_value(self):
        return self.spectrum
    


    @Command()
    def go(self):
        """generate new spectrum"""

        self.status = self.Status.BUSY, 'reading Spectrum'
        self.go_flag = True



    def getSpectrum(self):
        start = time.time()

        mass = np.random.randint(0,1000,num_spec)
        partial_pressure = np.random.randint(0,1000,num_spec)
        timestamp = np.linspace(start=start,stop=start+self.aquire_time,endpoint=False,num=num_spec)

        new_spectr = {
            'mass':mass.tolist(),
            'partial_pressure':partial_pressure.tolist(),
            'timestamp':timestamp.tolist()}
        
        return new_spectr

    def thread(self):
        self.spectrum = self.getSpectrum()
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

            time.sleep(1)
            self.read_value()

    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()

        

        


        
        