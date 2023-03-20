from frappy.datatypes import BoolType, EnumType, FloatRange, StringType, TupleOf, ArrayOf

from frappy.core import StatusType ,Command, Parameter, Readable, HasIO, StringIO,StructOf, Property, IDLE, BUSY, WARN, ERROR, IntRange, Drivable, nopoll

from frappy.lib.enum import Enum

from frappy.modules import Attached

import re
import time
import urx
import numpy as np


ROBOT_MODE_ENUM = {
    'NO_CONTROLLER'  :0,
    'DISCONNECTED'   :1,
    'CONFIRM_SAFETY' :2,
    'BOOTING'        :3,
    'POWER_OFF'      :4,
    'POWER_ON'       :5,
    'IDLE'           :6,
    'BACKDRIVE'      :7,
    'RUNNING'        :8
}


class RobotIO(StringIO):
    pass
    
    default_settings = {'port': 29999}
    pollinterval = 1
    wait_before = 0.05








class UR_Robot(HasIO,Drivable):
    _r = None
    _rt_data = None

    def initModule(self):
        super().initModule()
        
        nopref = self.io.uri 
        for i in range(30):
            try:
                ip = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',self.io.uri).group()
                self._r = urx.Robot(ip, use_rt=True, urFirm=5.1)
            
                
                break
            except:

                time.sleep(.5)
        
    
    attached_sample =  Attached(mandatory=True)
    
    attached_storage = Attached(mandatory=True)
    
    Status = Enum(
        Drivable.Status,
        PREPARING = StatusType.PREPARING,
        PAUSED = 304,
        STOPPED = 402,
        STANDBY = StatusType.STANDBY        
        )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    
    
    value = Parameter("Currently executing Program",
                       datatype=StringType(),
                       default = '<unknown>.urp',
                       readonly = True)

    target = Parameter("Program that is to be executed",
                       datatype=StringType(),
                       default = 'none',
                       readonly = False)
    
    loaded_prog = Parameter("Program that is currently loaded",
                            datatype= StringType(),
                            default = "<unknown>.urp",
                            readonly = True,
                            visibility = 'expert')
    
    model = Parameter("Model name of the robot",
                      datatype=StringType(),
                      default = "none",                
                      readonly = True,
                      group = "Robot Info")
    
    serial = Parameter("Serial number of connected robot",
                       datatype=StringType(),
                       default = "none",
                       readonly = True,
                       group = "Robot Info")
    
    ur_version = Parameter("Version number of the UR software installed on the robot",
                           datatype=StringType(),
                           default = "none",
                           readonly = True,
                           group = "Robot Info",
                           visibility = 'expert')
    
    robotmode = Parameter("Current mode of Robot",
                          datatype=EnumType("Robot Mode",ROBOT_MODE_ENUM),
                          default = "DISCONNECTED",
                          readonly = True,
                          group = "Robot Info")
    
    powerstate = Parameter("Powerstate of Robot",
                           datatype=EnumType("Pstate",POWER_OFF= None,POWER_ON = None ),
                           default = "POWER_OFF" ,
                           readonly = False)

    tcp_position = Parameter("Tool Center Point (TCP) Position x,y,z",
                      datatype=ArrayOf(FloatRange(unit = 'm'),3,3),
                      readonly = True,
                      group= "Tool Center Point")
    
    tcp_orientation = Parameter("Tool Center Point (TCP) Rotatiom Rx,Ry,Rz",
                      datatype=ArrayOf(FloatRange(unit = 'rad',fmtstr= '%.3f'),3,3),
                      readonly = True,
                      group= "Tool Center Point"
                    )
    joint_temperature = Parameter("Joint Temperatures of Robot",
                      datatype=ArrayOf(FloatRange(unit = 'K',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    joint_voltage = Parameter("Joint Voltages of Robot",
                      datatype=ArrayOf(FloatRange(unit = 'V',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    joint_current = Parameter("Joint Currents of Robot",
                      datatype=ArrayOf(FloatRange(unit = 'A',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    
    robot_voltage = Parameter("Voltage of Robot",
                      datatype=FloatRange(unit = 'V',fmtstr= '%.3f'),
                      readonly = True,
                      group = 'Robot Info'
                    )
    robot_current = Parameter("Current of Robot",
                      datatype=FloatRange(unit = 'A',fmtstr= '%.3f'),
                      readonly = True,
                      group = 'Robot Info'
                  
                    )
    
    stop_State = Parameter("Robot State when stop was pressed",
                           datatype=StructOf(stopped = BoolType(),
                                             interrupted_prog = StringType(),
                                             ),
                           visibility = 'expert',
                           default = {'stopped':False,'interrupted_prog':'none'}
                           )
    
    pause_State = Parameter("Robot State when pause was pressed",
                           datatype=StructOf(paused = BoolType(),
                                             interrupted_prog = StringType(),
                                             ),
                           visibility = 'expert',
                           default = {'paused':False,'interrupted_prog':'none'})
    
    def doPoll(self):
        self.read_value()
        self.read_status()
        self.read_tcp_position()
        self.read_tcp_orientation()
        self.read_joint_current()
        self.read_joint_voltage()
        self.read_robot_current()
        self.read_robot_voltage()
    
    
    def read_tcp_position(self):

        self._rt_data = self._r.get_all_rt_data()
        return self._rt_data['tcp'][0:3]
    
    def read_tcp_orientation(self):
        return self._rt_data['tcp'][3:6]
    
    def read_joint_temperature(self):    
        return  self._rt_data['joint_temperature']+273.15
    
    def read_joint_voltage(self):
        return self._rt_data['joint_voltage']
        
    def read_joint_current(self):
        return self._rt_data['joint_current']
        
    def read_robot_current(self):
        return self._rt_data['robot_current']
    
    def read_robot_voltage(self):
        return self._rt_data['robot_voltage']



    def write_target(self,target):
        old_prog_name = self.target
        load_reply = str(self.communicate(f'load {target}'))
        
        
        
        if re.match(r'Loading program: .*%s' % target,load_reply):
            self.status = IDLE, 'loaded Program: ' #+prog_name
            return target
           
        
        elif re.match(r'File not found: .*%s' % target,load_reply):
            self.status = WARN, 'Program not found: '+target
        
        elif re.match(r'Error while loading program: .*%s' % target,load_reply):
            self.status = WARN, 'ERROR while loading Program: '+ target
            
        else:
            self.status = WARN, 'unknown Answer: '+load_reply 
           
            
        return old_prog_name
    
    
    def run_program(self,prog_name):
        # PAUSED: continue loaded Program first
        # STOPPED: resolve STOPPED ERROR first
        if self.pause_State['paused']  or self.stop_State['stopped']:
            return False
            
        if self.write_target(prog_name) != prog_name:
            return False
        
        self.play()
        
        if self.status[0] == BUSY:
            return True
        
        return False   
            
    
    def read_loaded_prog(self):
        loaded_prog_reply =  str(self.communicate('get loaded program'))

        if loaded_prog_reply == 'No program loaded':
            return 'no_program_loaded'
        else:
            return re.search(r'([^\/]+.urp)',loaded_prog_reply).group()

        
    
    def read_value(self):
        if(self._program_running()):
            return self.read_loaded_prog()
        else:
            return 'none'     


    def read_model(self):
        return str(self.communicate('get robot model'))

    def read_serial(self):
        return str(self.communicate('get serial number'))
    

    def read_ur_version(self):
        return str(self.communicate('version'))
    
    def read_robotmode(self):
        return str(self.communicate('robotmode')).removeprefix('Robotmode: ')
    
    def read_powerstate(self):
        self.read_robotmode()
        if self.robotmode.value > 4:
            return 'POWER_ON' 
        else:
            return 'POWER_OFF'
    
    
    def write_powerstate(self,powerstate):
        p_str = powerstate.name
        
        self.communicate(POWER_STATE.get(p_str,None))
        
        if powerstate == 'POWER_ON':
            self.communicate('brake release')
        
        
        self.powerstate = self.read_powerstate()
        
        return powerstate.name

    
    def read_status(self):
        if self.pause_State['paused']:
            return PAUSED, 'Program execution paused'
        
        if self.stop_State['stopped']:
            return STOPPED, 'Program execution stopped'
                
        if self.status[0] == ERROR:
            return self.status
        
        if self.status[0] == UNKNOWN:
            return self.status
        
        

                
        if self._program_running() and 'RUNNING' == self.read_robotmode():
            return BUSY, 'Program running'    	    
        
        return ROBOT_MODE_STATUS[self.robotmode.name]


    @Command
    def stop(self):
        """Stop execution of program"""
        
        # already stopped
        if self.stop_State['stopped']:
            return
        
        stopped_struct = {'stopped' : self._program_running(), 'interrupted_prog' : self.value}
        
     
        stop_reply  = str(self.communicate('stop'))
        
        if stop_reply ==  'Stopped' and stopped_struct['stopped']:
            self.status = STOPPED, "Stopped Execution"
            
            # Rollback side effects of stopped Program
            if re.match(r'in\d+\.urp',stopped_struct['interrupted_prog']):
                pos = self.attached_storage.last_pos
                self.attached_storage.mag.removeSample(pos)
                 
            if re.match(r'out\d+\.urp',stopped_struct['interrupted_prog']):
                #Sample is already removed from internal structure
                pass
            
            if re.match(r'messpos\d+\.urp',stopped_struct['interrupted_prog']):
                pos = self.attached_sample.value
                self.attached_storage.mag.removeSample(pos)
                self.attached_sample.value = 0

            
            if re.match(r'messposin\d+\.urp',stopped_struct['interrupted_prog']):
                pos = self.attached_sample.value
                self.attached_storage.mag.removeSample(pos)
                self.attached_sample.value = 0
                
            if re.match(r'messen.urp',stopped_struct['interrupted_prog']):
                pos = self.attached_sample.value
                self.attached_storage.mag.removeSample(pos)
                self.attached_sample.value = 0
            
        elif stop_reply == 'Failed to execute: stop':
            self.status = ERROR, "Failed to execute: stop"
            return
            
        self.stop_State = stopped_struct
    
    @Command()
    def play(self):
        """Start/continue execution of program"""
        if self.stop_State['stopped']:
            return
        
        if self.pause_State['paused'] and self.pause_State['interrupted_prog'] != self.loaded_prog:
            self.status = ERROR, "Paused and loaded Program dont Match"
            self.pause_State = {'paused' : False, 'interrupted_prog' : self.loaded_prog}
            return
        
        play_reply  = str(self.communicate('play'))
        
        # Reset paused state
        self.pause_State = {'paused' : False, 'interrupted_prog' : self.loaded_prog}
        
        if play_reply == 'Starting program':
            self.status = BUSY, "Starting program"
            
            

        else:
            self.status = ERROR, "Failed to execute: play"

            
    @Command
    def pause(self):
        """Pause execution of program"""
        if self.stop_State['stopped']:
            return
        
        paused_struct = {'paused' : self._program_running(), 'interrupted_prog' : self.value}
        
        play_reply  = str(self.communicate('pause'))
        
        if play_reply == 'Pausing program':
            self.status = PAUSED, "Paused program execution"
        else:
            self.status = ERROR, "Failed to execute: pause"
            return
        
        self.pause_State = paused_struct
    
    def _program_running(self): 
        running_reply = str(self.communicate('running')).removeprefix('Program running: ') 
        
        if running_reply == 'true':
            return True
        else:
            return False	    
        
        
PAUSED     = UR_Robot.Status.PAUSED
STOPPED    = UR_Robot.Status.STOPPED
UNKNOWN    = Readable.Status.UNKNOWN
PREPARING = UR_Robot.Status.PREPARING
DISABLED   = UR_Robot.Status.DISABLED
STANDBY    = UR_Robot.Status.STANDBY 
        
    
ROBOT_MODE_STATUS = {
    'NO_CONTROLLER' :(ERROR,'NO_CONTROLLER'),
    'DISCONNECTED' :(DISABLED,'DISCONNECTED'),
    'CONFIRM_SAFETY' :(DISABLED,'CONFIRM_SAFETY'),
    'BOOTING' :(PREPARING,'BOOTING'),
    'POWER_OFF' :(DISABLED,'POWER_OFF'),
    'POWER_ON' :(STANDBY,'POWER_ON'),
    'IDLE' :(IDLE,'IDLE'),
    'BACKDRIVE' :(PREPARING,'BACKDRIVE'),
    'RUNNING' :(IDLE,'IDLE'),
}



ROBOT_PROG = {
 'initpos' : 'initpos.urp',
 'pos1' : 'prog1.urp',
 'pos2' : 'prog2.urp',
 'pos3' : 'prog3.urp'   
}

ROBOT_PROG_REVERSE = dict((v, k) for k, v in ROBOT_PROG.items())

POWER_STATE = {
    'POWER_ON'  : 'power on',
    'POWER_OFF' : 'power off'
}


