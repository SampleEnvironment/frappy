import time


from frappy.datatypes import FloatRange, StringType, StructOf, IntRange
from frappy.lib import clamp, mkthread
from frappy.modules import Command, Drivable, Parameter,Attached, Property
# test custom property (value.test can be changed in config file)





class PressureController(Drivable):
    meaning = Property(
        description="Module Meaning",
        datatype=StructOf(
            key = StringType(),
            link = StringType(),
            function = StringType(),
            importance= IntRange(0,50),
            belongs_to  = StringType()),
        export=True,
        extname='meaning')

    value   = Parameter("back pressure reactor section",FloatRange(min=0,max=5000),default = 0,unit = "mbar" )
    target  = Parameter("Desired back pressure",FloatRange(min=0,max=5000),default = 0,unit = "mbar" )
    ramp    = Parameter("desired ramp ",FloatRange(min=0,max=1000),default = 0,unit = "mbar/min" ,readonly = False)
    pollinterval = Parameter("polling interval",datatype=FloatRange(0), default=5)
    tolerance = Parameter("pressure range for stability checking",datatype=FloatRange(0,100),default = 5,unit = "mbar",readonly = False)


    
    attached_mfc1 = Attached(mandatory=True)
    attached_mfc2 = Attached(mandatory=True)
    attached_mfc3 = Attached(mandatory=True)

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
            
            mfc_flow = [self.attached_mfc1.value,
                        self.attached_mfc2.value,
                        self.attached_mfc3.value]
            
            massflow = True
            if (all(x == 0 for x in mfc_flow)):
                massflow = False
            
            if massflow or (not massflow and self.target < self.regulationFlow):
                self.regulationFlow = self.setpoint
            

                

            # temperature is stable when all recorded values in the window
            # differ from setpoint by less than tolerance

            if abs(self.regulationFlow - self.target) < self.tolerance:
                self.status = self.Status.IDLE, 'at target'
                damper -= (damper - 1) * 0.1  # max value for damper is 11
            else:
                if massflow or (not massflow and self.target < self.regulationFlow):
                    self.status = self.Status.BUSY, 'ramping setpoint'
                else:
                    self.status = self.Status.BUSY, 'unable to reach setpoint, no massflow'
            damper -= (damper - 1) * 0.05
            self.regulationFlow = round(self.regulationFlow, 4)

            timestamp = t
            self.read_value()

    def shutdownModule(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.is_alive():
            self._thread.join()
