from frappy.datatypes import BoolType, EnumType, FloatRange, StringType,  ArrayOf

from frappy.core import StatusType ,Command, Parameter,  HasIO, StringIO,StructOf,  IDLE, BUSY, ERROR, Drivable

from frappy.errors import IsErrorError, ReadFailedError, InternalError,   ImpossibleError, IsBusyError


from frappy.lib.enum import Enum

from frappy.modules import Attached

import re
import time
import urx



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

SAFETYSTATUS = {
    'NORMAL' :0,
    'REDUCED' :1,
    'PROTECTIVE_STOP' :2,
    'RECOVERY' :3,
    'SAFEGUARD_STOP' :4,
    'SYSTEM_EMERGENCY_STOP' :5,
    'ROBOT_EMERGENCY_STOP' :6,
    'VIOLATION' :7,
    'FAULT' :8,
    'AUTOMATIC_MODE_SAFEGUARD_STOP' :9,
    'SYSTEM_THREE_POSITION_ENABLING_STOP' :10,
    'UNKNOWN':11

} 


RESET_PROG = 'reset.urp'

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
        DISABLED = StatusType.DISABLED,
        PREPARING = StatusType.PREPARING,
        PAUSED = 305,
        UNKNOWN = StatusType.UNKNOWN,
        STOPPED = 402,
        STANDBY = StatusType.STANDBY,
        LOCAL_CONTROL = 403,
        LOCKED = 404        
                
        )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    
    
    value = Parameter("Currently loaded program",
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
    
    robotmode = Parameter("Current mode of robot",
                          datatype=EnumType("Robot Mode",ROBOT_MODE_ENUM),
                          default = "DISCONNECTED",
                          readonly = True,
                          group = "Status Info")
    
    powerstate = Parameter("Powerstate of robot",
                           datatype=EnumType("Pstate",POWER_OFF= None,POWER_ON = None ),
                           default = "POWER_OFF" ,
                           readonly = False,
                           group = "Status Info")
    
    safetystatus = Parameter("Safetystatus: Specifying if a given Safeguard Stop was caused by the permanent safeguard I/O stop,a configurable I/O automatic mode safeguard stop or a configurable I/O three position enabling device stop.",
                             datatype=EnumType(SAFETYSTATUS),
                             default = "NORMAL",
                             readonly = True,
                             group = 'Status Info')

    tcp_position = Parameter("Tool Center Point (TCP) position x,y,z",
                      datatype=ArrayOf(FloatRange(unit = 'm'),3,3),
                      readonly = True,
                      group= "Tool Center Point")
    
    tcp_orientation = Parameter("Tool Center Point (TCP) rotatiom Rx,Ry,Rz",
                      datatype=ArrayOf(FloatRange(unit = 'rad',fmtstr= '%.3f'),3,3),
                      readonly = True,
                      group= "Tool Center Point"
                    )
    joint_temperature = Parameter("Joint temperatures of robot",
                      datatype=ArrayOf(FloatRange(unit = 'K',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    joint_voltage = Parameter("Joint voltages of robot",
                      datatype=ArrayOf(FloatRange(unit = 'V',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    joint_current = Parameter("Joint currents of robot",
                      datatype=ArrayOf(FloatRange(unit = 'A',fmtstr= '%.3f'),6,6),
                      readonly = True,
                      group = 'Joint Info'
                    )
    
    robot_voltage = Parameter("Voltage of robot",
                      datatype=FloatRange(unit = 'V',fmtstr= '%.3f'),
                      readonly = True,
                      group = 'Robot Info'
                    )
    robot_current = Parameter("Current of robot",
                      datatype=FloatRange(unit = 'A',fmtstr= '%.3f'),
                      readonly = True,
                      group = 'Robot Info'
                  
                    )
    

    
    is_in_remote_control = Parameter("Control status of robot arm",
                                     datatype=BoolType,
                                     readonly = True,
                                     default = False,
                                     group = 'Status Info')
    
    
    stop_State = Parameter("Robot state when stop was pressed",
                           datatype=StructOf(stopped = BoolType(),
                                             interrupted_prog = StringType(),
                                             ),
                           visibility = 'expert',
                           default = {'stopped':False,'interrupted_prog':'none'}
                           )
    
    pause_State = Parameter("Robot state when pause was pressed",
                           datatype=StructOf(paused = BoolType(),
                                             interrupted_prog = StringType(),
                                             ),
                           visibility = 'expert',
                           default = {'paused':False,'interrupted_prog':'none'})
    
    
    def doPoll(self):
        self.read_value()
        self.read_status()

    
    
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

    def read_is_in_remote_control(self):
        remote_control =  str(self.communicate('is in remote control'))
        
        if remote_control == 'true':
            return True
        return False

    def read_safetystatus(self):
        safety_stat = str(self.communicate('safetystatus')).removeprefix("Safetystatus: ")

        if safety_stat in SAFETYSTATUS:
            return safety_stat

        raise ReadFailedError("Unknown safetytatus:" + safety_stat)

    def write_target(self,target):
        # Is Robot in remote control Mode?        
        
        if self.safetystatus > SAFETYSTATUS['REDUCED']:
            raise IsErrorError('Robots is locked due to a safety related problem (' + str(self.safetystatus.name) + ") Please refer to instructions on the controller tablet or try 'clear_error' command.")
            
        
        if not self.is_in_remote_control:
            raise ImpossibleError('Robot arm is in local control mode, please switch to remote control mode on the Robot controller tablet')
        
        # Is the Robot in a stpped state?
        if self.stop_State['stopped']:
            raise IsErrorError('cannot run program when execution was Stopped, please reset and check for consistency')
        
        if self.pause_State['paused']:
            raise IsBusyError("continue loaded program before executing "+ target)
        
        if self.status[0] == BUSY or self.status[0] == PREPARING:
            raise IsBusyError('Robot is already executing another program')
        
        if self.status[0] >= 400 and self.status[0] != STOPPED:
            raise IsErrorError("Robot is in an error state. program '"+target+ "' cannot be exectuted")
        
        load_reply = str(self.communicate(f'load {target}'))
              
        
        if re.match(r'Loading program: .*%s' % target,load_reply):
            self._run_loaded_program()
            self.value = target
            return target
           
        elif re.match(r'File not found: .*%s' % target,load_reply):
            raise InternalError('Program not found: '+target)
        
        elif re.match(r'Error while loading program: .*%s' % target,load_reply):
            raise InternalError('write_target ERROR while loading program: '+ target)
            
        else:
            self.status = ERROR, 'unknown answer: '+ load_reply 
            raise InternalError('unknown answer: '+load_reply) 
        
        
    
    
    def _run_loaded_program(self):
        play_reply  = str(self.communicate('play'))
        

        
        if play_reply == 'Starting program':
            # Reset paused state
            self.pause_State = {'paused'  : False, 'interrupted_prog' : self.loaded_prog}
            self.stop_State  = {'stopped' : False, 'interrupted_prog' : self.loaded_prog}
            self.status = BUSY, "Starting program"
        else:
            raise InternalError("Failed to execute: play")
        
    
    def read_loaded_prog(self):
        loaded_prog_reply =  str(self.communicate('get loaded program'))

        if loaded_prog_reply == 'No program loaded':
            return 'no_program_loaded'
        else:
            return re.search(r'([^\/]+.urp)',loaded_prog_reply).group()

        
    
    def read_value(self):
        return self.read_loaded_prog()



    def read_model(self):
        return str(self.communicate('get robot model'))

    def read_serial(self):
        return str(self.communicate('get serial number'))
    

    def read_ur_version(self):
        return str(self.communicate('version'))
    
    def read_robotmode(self):
        robo_mode =  str(self.communicate('robotmode')).removeprefix('Robotmode: ')
    
        if robo_mode in ROBOT_MODE_ENUM:
            return robo_mode

        raise ReadFailedError("Unknown robot mode:" + robo_mode)
    
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
    
        
        if not self.read_is_in_remote_control():
            return LOCAL_CONTROL, "Robot is in 'local control' mode"

        self.read_safetystatus()
        if  self.safetystatus > 1:
            return LOCKED, str(self.safetystatus.name)
               
        if self.pause_State['paused']:
            return PAUSED, 'Program execution paused'
        
        if self.stop_State['stopped']:
            return STOPPED, 'Program execution stopped'
                
        if self.status[0] == ERROR:
            return self.status
        
        if self.status[0] == UNKNOWN:
            return self.status
        
        

                
        if self._program_running() and 'RUNNING' == self.read_robotmode():
            if self.value == RESET_PROG:
                return BUSY , 'resetting robot'
            
            return BUSY, 'Program running'    	    
        
        return ROBOT_MODE_STATUS[self.robotmode.name]

    def _program_running(self): 
        running_reply = str(self.communicate('running')).removeprefix('Program running: ') 
        
        if running_reply == 'true':
            return True
        
        return False	    
        
    

    @Command(group ='control')
    def stop(self):
        """Stop execution of program"""
        
        # already stopped
        if self.stop_State['stopped']:
            raise ImpossibleError('module is already stopped')
        
        stopped_struct = {'stopped' : self._program_running(), 'interrupted_prog' : self.value}
        
     
        stop_reply  = str(self.communicate('stop'))
        
        if stop_reply ==  'Stopped' and stopped_struct['stopped']:
            self.status = STOPPED, "Stopped execution"
            
            # Rollback side effects of stopped Program
            if re.match(r'in\d+\.urp',stopped_struct['interrupted_prog']):
                pos = self.attached_storage.last_pos
                self.attached_storage.mag.removeSample(pos)
                 
            if re.match(r'out\d+\.urp',stopped_struct['interrupted_prog']):
                #Sample is already removed from internal structure
                pass
            
            if re.match(r'messout.urp',stopped_struct['interrupted_prog']):
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
            raise InternalError("Failed to execute: stop")
            
            
            
        self.stop_State = stopped_struct
    
    @Command(group ='control')
    def play(self):
        """Start/continue execution of program"""
        
        if self.safetystatus > SAFETYSTATUS['REDUCED']:
            raise IsErrorError('Robots is locked due to a safety related problem: ' + str(self.safetystatus) )
        
        # Is Robot in remot control Mode?        
        if not self.is_in_remote_control:
            raise ImpossibleError('Robot arm is in local control mode, please change control mode on the robot controller tablet')
        
        
        if self.status[0] == BUSY or self.status[0] == PREPARING:
            raise IsBusyError('Robot is already executing another program')
        
        if self.stop_State['stopped']:
            raise IsErrorError('cannot run program when stopped')
        
        if self.pause_State['paused'] and self.pause_State['interrupted_prog'] != self.loaded_prog:
            self.pause_State = {'paused' : False, 'interrupted_prog' : self.loaded_prog}
            raise ImpossibleError("Paused and loaded program dont match")
                    
        self._run_loaded_program()
            
    @Command(group ='control')
    def pause(self):
        """Pause execution of program"""
              
        if self.stop_State['stopped']:
            raise IsErrorError('cannot pause program when stopped')
        
        if not self._program_running():
            raise ImpossibleError('Currently not executing a program')
        
        paused_struct = {'paused' : True, 'interrupted_prog' : self.value}
        
        play_reply  = str(self.communicate('pause'))
        
        if play_reply == 'Pausing program':
            self.status = PAUSED, "Paused program execution"
        else:
            raise InternalError("Failed to execute: pause")
            
        
        self.pause_State = paused_struct
    
    @Command(visibility = 'expert',group ='error_handling')
    
    def clear_error(self):
        """Trys to Clear Errors and resets module to a working IDLE state (a subsequent reset() is recommended)"""
        if self.status[0] == STOPPED:
            self.stop_State = {'stopped' : False, 'interrupted_prog' : self.value}
            self.status = IDLE
            
            
            
        if self.status[0] == LOCKED and self.safetystatus.name == 'PROTECTIVE_STOP':
            # try unlocking protective Stop
            unlock_reply = str(self.communicate("unlock protective stop"))
            
            if unlock_reply == "Protective stop releasing":
                self.communicate('close safety popup')
                self.status = IDLE
                return
                
            raise ImpossibleError('Cannot unlock protective stop until 5s after occurrence. Always inspect cause of protective stop before unlocking')
                
                
            
        
            
    
    @Command(visibility ='expert',group ='error_handling' )
    def reset(self):
        """Reset Robot Module (Returns to Home Position)"""
        
        self.write_target(RESET_PROG)
        
        # Robot was holding a sample before
        if self.attached_sample._holding_sample():
            # remove sample from Storage (robot just dropped it)
            try:
                self.attached_storage.mag.removeSample(self.attached_sample.value)
            except:
                pass # Sample was already not holding a sample
            # set sample.value to zero --> robot not holding a Sample
            self.attached_sample.target = 0
            self.attached_sample.value = 0
            
            

            
            
    
  
PAUSED           = UR_Robot.Status.PAUSED
STOPPED          = UR_Robot.Status.STOPPED
UNKNOWN          = UR_Robot.Status.UNKNOWN
PREPARING        = UR_Robot.Status.PREPARING
DISABLED         = UR_Robot.Status.DISABLED
STANDBY          = UR_Robot.Status.STANDBY 
LOCAL_CONTROL    = UR_Robot.Status.LOCAL_CONTROL 
LOCKED           = UR_Robot.Status.LOCKED
ERROR            = UR_Robot.Status.ERROR

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



POWER_STATE = {
    'POWER_ON'  : 'power on',
    'POWER_OFF' : 'power off'
}


