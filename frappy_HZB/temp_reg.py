import time


from frappy.datatypes import FloatRange, StringType
from frappy.lib import clamp, mkthread
from frappy.modules import Command, Drivable, Parameter,Attached,Readable
# test custom property (value.test can be changed in config file)





class TemperatureController(Drivable):
    value   = Parameter("Heater temperature at reactor cell",FloatRange(minval=0,maxval=5000),default = 0,unit = "K" )
    target  = Parameter("desired heater temperature at reactor cell",FloatRange(minval=0,maxval=5000),default = 0,unit = "K" )
    ramp    = Parameter("desired ramp speed for the heater temperature",FloatRange(minval=0,maxval=1000),default = 0,unit = "K/min" ,readonly = False)
    pollinterval = Parameter("polling interval",datatype=FloatRange(0), default=5)
    tolerance = Parameter("Temperature range for stability checking",datatype=FloatRange(0,100),default = 5,unit = "K")



    looptime = Parameter("timestep for simulation",
        datatype=FloatRange(0.01, 10), unit="s", default=1,
        readonly=False, export=False)

    def initModule(self):
        super().initModule()
        self._stopflag = False
        self._thread = mkthread(self.thread)

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status

    def read_value(self):
        # return regulation value (averaged regulation flow)
        return self.regulationFlow 

    def read_target(self):
        return self.target

    def write_target(self, value):
        value = round(value, 2)
        if value == self.target:
            # nothing to do
            return value
        self.target = value
        # next read_status will see this status, until the loop updates it
        self.status = self.Status.BUSY, 'new target set'
        return value
    


    


    @Command()
    def stop(self):
        """Stop ramping the setpoint

        by setting the current setpoint as new target"""
        # XXX: discussion: take setpoint or current value ???
        self.write_target(self.setpoint)


    def thread(self):
        self.regulationFlow = 0
        self.status = self.Status.IDLE, ''
        while not self._stopflag:
            try:
                self.__sim()
            except Exception as e:
                self.log.exception(e)
                self.status = self.Status.ERROR, str(e)

    def __sim(self):
        # complex thread handling:
        # a) simulation of cryo (heat flow, thermal masses,....)
        # b) optional PID temperature controller with windup control
        # c) generating status+updated value+ramp
        # this thread is not supposed to exit!

        self.setpoint = self.target
        # local state keeping:
        regulation = self.regulationFlow

        # keep history values for stability check
        timestamp = time.time()
        damper = 1

        while not self._stopflag:
            t = time.time()
            h = t - timestamp
            if h < self.looptime / damper:
                time.sleep(clamp(self.looptime / damper - h, 0.1, 60))
                continue
            # a)



            # c)
            if self.regulationFlow != self.target:
                if self.ramp == 0 :
                    maxdelta = 1000
                else:
                    maxdelta = self.ramp / 60. * h
                try:
                    self.setpoint = round(self.setpoint + clamp(self.target - self.setpoint, -maxdelta, maxdelta), 4)
                    self.log.debug('setpoint changes to %r (target %r)',
                                   self.setpoint, self.target)
                except (TypeError, ValueError):
                    # self.target might be None
                    pass
            
                self.regulationFlow = self.setpoint
            

                

            # temperature is stable when all recorded values in the window
            # differ from setpoint by less than tolerance

            if abs(self.regulationFlow - self.target) < self.tolerance:
                self.status = self.Status.IDLE, 'at target'
                damper -= (damper - 1) * 0.1  # max value for damper is 11
            else:
                self.status = self.Status.BUSY, 'ramping setpoint'

            damper -= (damper - 1) * 0.05
            self.regulationFlow = round(self.regulationFlow, 4)

            timestamp = t
            self.read_value()

    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()


class TemperatureSensor(Readable):
    value   = Parameter("Heater temperature at reactor cell",
                        FloatRange(minval=0,maxval=5000),
                        default = 0,
                        unit = "K" )    

    pollinterval = Parameter("polling interval",datatype=FloatRange(0), default=5)

    heat_flux = Parameter("Constant for simulation of heat flux",
                          datatype=FloatRange(0,20),
                          default= 0.05,
                          readonly = False)


    looptime = Parameter("timestep for simulation",
        datatype=FloatRange(0.01, 10), unit="s", default=1,
        readonly=False, export=False)
    
    attached_temp_reg = Attached(mandatory=True)

    def initModule(self):
        super().initModule()
        self._stopflag = False
        self._thread = mkthread(self.thread)

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status

    def read_value(self):
        # return regulation value (averaged regulation flow)
        return self.sample_temp 



    


    


    @Command()
    def stop(self):
        """Stop ramping the setpoint

        by setting the current setpoint as new target"""
        # XXX: discussion: take setpoint or current value ???
        pass


    def thread(self):
        self.sample_temp = 0
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
            t = time.time()
            h = t - timestamp
            if h < self.looptime / damper:
                time.sleep(clamp(self.looptime / damper - h, 0.1, 60))
                continue
            # a)

            old_temp = self.value
            surround_temp = self.attached_temp_reg.value

            new_temp = old_temp - h *(old_temp - surround_temp) * self.heat_flux



                         


            damper -= (damper - 1) * 0.05
            self.sample_temp = round(new_temp, 6)

            timestamp = t
            self.read_value()

    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()
