


from frappy.modules import Command, Readable,Drivable, Parameter
from frappy.core import IDLE,BUSY
from frappy.datatypes import BoolType, EnumType, FloatRange, StringType, TupleOf,ArrayOf,Enum,StructOf,StatusType,IntRange

from frappy.errors import    ImpossibleError, IsBusyError

class Robot(Readable):
    value = Parameter("Robot Gripper Position",
                      datatype=StructOf(
                          x = FloatRange(),
                          y = FloatRange(),
                          z = FloatRange()),
                          default = {'x' : 0,'y':0,'z':0})
    
    Status = Enum(
        Drivable.Status,
        LOADING=303,
        UNLOADING = 304,
        PAUSED = 305,
        STOPPED = 402,
        LOCAL_CONTROL = 403,
        LOCKED = 404 
        )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    def read_value(self):
        #TODO
        #return self.robot.read_joint_angles()

        return {'x' : 0,'y':0,'z':0}  

    def read_status(self):
        #TODO 
        # robot_stat =self.robot.status
        # mapping robot_stat --> self.status SECoP Status (BUSY, IDLE...)
        
        return self.status       


    def initModule(self):
        super().initModule()
        #TODO 
        # Init Robot Client something like this:
        # self.robot = UniversalRobot(IP_ROBOT)#
        pass

    @Command(argument=IntRange(min=0,max=12),description = 'unload description')
    def load(self,sample_num):
        if self.status[0] >= BUSY:
            raise IsBusyError('cannot load robot is busy')
        

        # Dispatch to run in different Thread
        # self.robot.load(sample_num)
        pass

    @Command(argument=IntRange(min=0,max=12),description = 'unload description')
    def unload(self,sample_num):
        if self.status[0] >= BUSY:
            raise IsBusyError('cannot unload robot is busy')

        # Dispatch to run in different Thread
        # self.robot.unload(sample_num)
        pass