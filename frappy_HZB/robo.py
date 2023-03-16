from frappy.datatypes import BoolType, EnumType, FloatRange, StringType, TupleOf, ArrayOf

from frappy.core import Command, Parameter, Readable, HasIO, StringIO,StructOf, Property, IDLE, BUSY, WARN, ERROR, IntRange, Drivable, nopoll

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
        for i in range(30):
            try:
         
                self._r = urx.Robot("192.168.56.3", use_rt=True, urFirm=5.1)
                

                break
            except:
                print('Error')
                time.sleep(.5)
        
    
    value = Parameter("current loaded Program",
                       datatype=StringType(),
                       default = '<unknown>.urp',
                       readonly = True)

    target = Parameter("Sample number to retrieve",
                       datatype=StringType(),
                       default = 'none',
                       readonly = False)
    
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
                           group = "Robot Info")
    
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



    def write_target(self,prog_name):
        old_prog_name = self.target
        load_reply = str(self.communicate(f'load {prog_name}'))
        
        
        
        if re.match(r'Loading program: .*%s' % prog_name,load_reply):
            self.status = BUSY, 'loaded Program: ' #+prog_name
            play_reply = self.communicate('play')
                
            
            if play_reply.__eq__('Starting program'):
                self.status = BUSY, 'running Program: '# +prog_name
                self.value = prog_name
                return prog_name
            else:
                self.status = ERROR, 'Failed to execute: ' + prog_name         
            
        
        elif re.match(r'File not found: .*%s' % prog_name,load_reply):
            self.status = ERROR, 'Program not found: '+prog_name
        
        elif re.match(r'Error while loading program: .*%s' % prog_name,load_reply):
            self.status = ERROR, 'ERROR while loading Program: '+ prog_name
            
        else:
            self.status = ERROR, 'unknown Answer: '+load_reply 
           
            
        return old_prog_name
    
    


        
    
    def read_value(self):
        loaded_prog_reply =  str(self.communicate('get loaded program'))

        if loaded_prog_reply.__eq__('No program loaded'):
            return 'no_program_loaded'
        else:
            prog_name = re.search(r'([^\/]+.urp)',loaded_prog_reply).group()

            return prog_name
            


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
        self.read_robotmode()
                
        if self._program_running():
            return BUSY, 'Program running'    	    
        return ROBOT_MODE_STATUS[self.robotmode.name]


    @Command
    def stop(self):
        """Stop execution of program"""
        stop_reply  = str(self.communicate('stop'))
        
        if stop_reply.__eq__('Stopped'):
            self.status = IDLE, "Stopped Execution"
        else:
            self.status = ERROR, "Failed to execute: stop"
    
    @Command
    def play(self):
        """Start execution of program"""
        play_reply  = str(self.communicate('play'))
        
        if play_reply.__eq__('Starting program'):
            self.status = BUSY, "Starting program"
        else:
            self.status = ERROR, "Failed to execute: play"
            
    @Command
    def pause(self):
        """Pause execution of program"""
        play_reply  = str(self.communicate('pause'))
        
        if play_reply.__eq__('Pausing program'):
            self.status = IDLE, "Pausing program"
        else:
            self.status = ERROR, "Failed to execute: pause"
    
    def _program_running(self): 
        running_reply = str(self.communicate('running')).removeprefix('Program running: ') 
        
        if running_reply == 'true':
            return True
        else:
            return False	    
        
    
ROBOT_MODE_STATUS = {
    'NO_CONTROLLER' :(ERROR,'NO_CONTROLLER'),
    'DISCONNECTED' :(0,'DISCONNECTED'),
    'CONFIRM_SAFETY' :(0,'CONFIRM_SAFETY'),
    'BOOTING' :(0,'BOOTING'),
    'POWER_OFF' :(0,'POWER_OFF'),
    'POWER_ON' :(WARN,'POWER_ON'),
    'IDLE' :(IDLE,'IDLE'),
    'BACKDRIVE' :(IDLE,'BACKDRIVE'),
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

        
        