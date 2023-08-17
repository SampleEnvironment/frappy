
from frappy.datatypes import  EnumType, FloatRange, StringType, ArrayOf,StatusType

from frappy.core import Command, Parameter, Readable, HasIO,StructOf, IDLE, BUSY,  IntRange, Drivable

from frappy.errors import    ImpossibleError, IsBusyError

from frappy.lib.enum import Enum


from frappy.modules import Attached

import re
import uuid


nsamples = 12


SCHOKO_SORTEN = {
    'Knusperkeks':0,
    'Edel-Vollmilch':1,
    'Knusperflakes':2,
    'Nuss-Splitter':3,
    'Nugat':4,
    'Marzipan':5,
    'Joghurt':6,
}

SCHOKO_SORTEN_ENUM = {
    'Knusperkeks':0,
    'Edel-Vollmilch':1,
    'Knusperflakes':2,
    'Nuss-Splitter':3,
    'Nugat':4,
    'Marzipan':5,
    'Joghurt':6,
    'unknown':7
}

SCHOKO_FARBE = {
    'Knusperkeks':'brown',
    'Edel-Vollmilch':'blue',
    'Knusperflakes':'yellow',
    'Nuss-Splitter':'green',
    'Nugat':'dark blue',
    'Marzipan':'red',
    'Joghurt':'white',
    'unknown':'none'
}



SCHOKO_TO_SUBSTANCE_ID = {
    'Knusperkeks':0,
    'Edel-Vollmilch':1,
    'Knusperflakes':2,
    'Nuss-Splitter':3,
    'Nugat':4,
    'Marzipan':5,
    'Joghurt':6,
    'unknown':7
}









#TODO describe None {...} -->  describe . {...}

class SchokiStructOf(StructOf):
    def __init__(self, nsamples):
        super().__init__(
                        sample_name = StringType(), 
                        substance = StringType(),
                        substance_code = StringType(),
                        sample_pos =IntRange(minval= 0,maxval=nsamples),                        
                        manufacturer = StringType(),
                        sample_id = StringType(),
                        color = StringType(),
                        mass = FloatRange(minval=0,maxval=1,unit = 'kg')
                        )

class Schoki:
    def __init__(self, substance,samplePos,sample_name = None, substance_code = None, Manufacturer = None ,color = None,sample_id = None,mass =None ) -> None:
        self.substance = substance
        self.sample_name = sample_name
        self.samplePos =samplePos
        
        self.substance_code = substance_code
        self.Manufacturer = Manufacturer
        self.color = color
        self.sample_id = sample_id
        self.mass = mass
        
        if substance_code == None:
            self.substance_code = SCHOKO_SORTEN[substance]
        if Manufacturer == None:
            self.Manufacturer = 'Rittersport'
        if color == None:
            self.color = SCHOKO_FARBE.get(self.substance,None)
        if sample_id == None:
            self.sample_id = str(uuid.uuid4())
        if mass == None:
            self.mass = 0.0167
        if sample_name == None:
            self.sample_name = self.substance + self.Manufacturer        
    def toStructOf(self):

        return {'sample_name' : self.sample_name,
                'substance' : self.substance,
                'substance_code': str(self.substance_code),
                'sample_pos':self.samplePos,
                'manufacturer':self.Manufacturer,
                'sample_id':self.sample_id,
                'color': self.color,
                'mass':self.mass
                }
        
        
        
class Magazin:

    
    def __init__(self,nSamples):
        self.Mag = [None] * nSamples
          
        
    def insertSample(self,sample):                   
        if self.Mag[sample.samplePos-1]:
            raise Exception("Sample Pos already occupied")
        else:
            self.Mag[sample.samplePos-1] = sample
                
            
    def removeSample(self,samplePos):            
        if self.Mag[samplePos-1] == None:
            raise Exception("No sample at Pos "+ (samplePos-1)+"already occupied")
        else: 
            sample = self.Mag[samplePos-1]
            self.Mag[samplePos-1] = None 
            return sample       
    
    def get_sample(self,samplePos):
        return self.Mag[samplePos-1]        

            
    def mag2Arrayof(self):
        storage_arr = []
        for sample in  self.Mag:
            if sample:
                storage_arr.append(sample.toStructOf())
            
        return storage_arr



class Sample(HasIO,Drivable):
    
    Status = Enum(Drivable.Status,
                  DISABLED = StatusType.DISABLED,
                  PREPARING = StatusType.PREPARING,
                  HOLDING_SAMPLE = 101, 
                  MOUNTING=301,
                  UNMOUNTING = 302,
                  UNLOADING = 304,
                  MEASURING = 303,
                  PAUSED = 305,
                  UNKNOWN = 401,
                  STOPPED = 402,
                  LOCAL_CONTROL = 403,
                  LOCKED = 404 
                  )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    attached_robot = Attached(mandatory = True)
    attached_storage = Attached(mandatory = True)
    

    
    value = Parameter("Active Sample currently held by robot arm (0 == no sample)",
                      datatype=IntRange(minval=0,maxval=nsamples),
                      readonly = True,
                      default = 0) 

    target =  Parameter("Target Sample to be held by robot arm",
                      datatype=IntRange(minval=0,maxval=nsamples),
                      default = 0)
    
    sample_struct = Parameter("Sample, in JSON-Object representation",
                    datatype=SchokiStructOf(nsamples),
                    readonly = True,
                    group = 'sample') 
    
    sample_name = Parameter("Name of Sample currently held by robot Arm",
                            datatype=StringType(),
                            default = 'none',
                            group = 'sample',
                            readonly = True)
    
    substance = Parameter("Sample substance currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    substance_code = Parameter("substance_code of Sample currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    manufacturer = Parameter("Manufacturer of Sample currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    sample_id = Parameter("ID assigned to sample currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    color = Parameter("Color of sample currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    mass = Parameter("Mass of sample currently held my robot Arm",
                     datatype=FloatRange(minval=0,maxval=1,unit = 'kg'),
                     default = 0,
                     readonly= True,
                     group = 'sample')
    
    
    def read_value(self):
        return self.value
       
    def read_target(self):
        return self.target
    
    def write_target(self,target):
        
           
        ### Mount:
        if target != 0:
            self._mount(target)
        ### Unmount:
        if target == 0:
            self._unmount(target)
            
        return target
    
    
    def read_status(self):
        robo_stat = self.attached_robot.status
        
        
        # Robot Idle and sample in Gripper
        if robo_stat[0] == IDLE and self._holding_sample():
            
            return HOLDING_SAMPLE , "IDLE with Sample in Gripper"
        
        # Robot Arm is Busy        
        if robo_stat[0] == BUSY:
            if re.match(r'messpos\d+\.urp',self.attached_robot.value):
                return  MOUNTING, "Mounting Sample"
            if re.match(r'messposin\d+\.urp',self.attached_robot.value):
                return UNMOUNTING , "Unmounting Sample"
            if re.match(r'messen+\.urp',self.attached_robot.value):
                return MEASURING , "Measuring Sample"
            if re.match(r'messout+\.urp',self.attached_robot.value):
                return UNLOADING , "Unloading Sample"
            
            # Robot Running and No sample in Gripper
            return BUSY , "Robot is in use by other module"
        
        return robo_stat
    

    def read_sample_struct(self):
        if self._holding_sample():
            current_sample = self._get_current_sample()
            return current_sample.toStructOf()
        
        return {'sample_name':'none',
                'substance' : 'none',
                'substance_code':'none',
                'sample_pos': 0,
                'manufacturer':'none',
                'sample_id':'none',
                'color': 'none',
                'mass':0
                }
    
    def read_sample_name(self):
        if self._holding_sample():
           sample = self._get_current_sample()
           return str(sample.sample_name)
        return 'none'
    
    def read_substance_code(self):
       if self._holding_sample():
           sample = self._get_current_sample()
           return str(sample.substance_code)
       return 'none'
      
    def read_substance(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.substance
        return 'none'
    
    def read_color(self):
        if self._holding_sample() :
            sample = self._get_current_sample()
            return sample.color
        return 'none'
    
    def read_sample_id(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.sample_id
        return 'none'
   
    def read_manufacturer(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.Manufacturer
        return 'none'
    
    def read_mass(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.mass
        return 0
    
    def _holding_sample(self):
        if self.value == 0:
            return False
        return True
           
    def _get_current_sample(self):
        return self.attached_storage.mag.get_sample(self.value)
    
    def _check_value_consistency(self):
        if not self._get_current_sample():
            self.status = ERROR, "inconsistent storage! expected sample object at pos:" + str(self.value)
            raise ImpossibleError('no sample stored at Pos: ' +str(self.value)+'! please, check sample objects stored in storage' )
        
    def _mount(self,target):
        """Mount Sample to Robot arm"""
        assert(target != 0)
        
        # check if sample is present in Storage
        if not self.attached_storage.mag.get_sample(target):
            raise ImpossibleError('no sample stored at pos: ' +str(target)+'! please, check sample objects stored in storage' )
        
        
        # check if robot is currently holding a Sample from Storage
        if self._holding_sample():
            raise ImpossibleError('Gripper is already holding sample' + str(self.value))       
     
        # Run Robot script to mount actual Sample        
        prog_name = 'messpos'+ str(target) + '.urp'
        
        assert(re.match(r'messpos\d+\.urp',prog_name) )
        
        self.attached_robot.write_target(prog_name)
 
        self.status = MOUNTING , "Mounting Sample: " + str(target)
        
        self.target = target
        
        # Robot successfully mounting the sample
        self.value = self.target
     

    def _unmount(self,target):
        """Unmount Sample to Robot arm"""
        
        assert(target == 0)
        
        # check if sample is present in Storage
        self._check_value_consistency()
        
        # check if robot is ready to mount sample
        if not self._holding_sample():
            raise ImpossibleError('Gripper is currently not holding a sample, cannot unmount')   
        
        
        # Run Robot script to unmount Sample        
        prog_name = 'messposin'+ str(self.value) + '.urp'
        
        assert(re.match(r'messposin\d+\.urp',prog_name) )
        
        self.attached_robot.write_target(prog_name)

        self.status = UNMOUNTING , "Unmounting Sample: " + str(self.value)
        
        self.target = target
        # Robot successfully unmounted the sample
        self.value = 0
        

    @Command
    def measure(self):
        """Measure Sample held by Robot arm"""

        # check if robot is holding a sample
        if not self._holding_sample():
            raise ImpossibleError('Cannot measure: gripper is currently not holding a sample')
            
        
        if self.attached_robot.status[0] != IDLE:
            raise IsBusyError('Robot arm is in use by another module')  
            
        
        # check if Sample is present in Storage
        self._check_value_consistency()


        
        # Run Robot script to unmount Sample        
        prog_name = 'messen.urp'   
  
        
        self.attached_robot.write_target(prog_name)
        
       
        self.status = MEASURING , "Measuring Sample: " + str(self.value)
        
    @Command()
    def unload(self):
        """"Unload Sample currently held by Robot"""
         # check if robot is holding a sample
        if not self._holding_sample():
            raise ImpossibleError('Gripper is currently not holding a sample')
            
        
        if self.attached_robot.status[0] != IDLE:
            raise IsBusyError('Robot arm is not ready to be used')  
            
        
        # check if Sample is present in Storage
        self._check_value_consistency()
        
        # Run Robot script to unmount Sample        
        prog_name = 'messout.urp'   
  
        
        self.attached_robot.write_target(prog_name)
        
      
        self.status = UNLOADING , "Unloading Sample"
        
        try:
            self.attached_storage.mag.removeSample(self.value)
        except:
            raise ImpossibleError( "No sample stored at array Pos " + str(self.value))
        
        self.value = 0
        self.target = 0
        
        
    
    @Command
    def stop(self):
        """Stop execution of program"""
        self.attached_robot.stop()

    @Command(visibility = 'expert',group ='error_handling')
    def reset(self):
        """Reset sample module (remove sample from gripper)"""
        self.attached_robot.reset()
        
        
        
 
    
    @Command(visibility = 'expert',group ='error_handling')
    def clear_error(self):
        """Trys to Clear Errors"""
        self.reset()
        self.attached_robot.clear_error()
        
    # @Command(group = 'admin commands',visibility = 'expert')
    # def force_mount(self):
    #     """unmount Sample to Robot without calling robot program"""
    #     pass
    
    # @Command(group = 'admin commands',visibility = 'expert')
    # def force_unmount(self):
    #     """unmount Sample to Robot without calling robot program"""
    #     pass
    
    
    
    
class Storage(HasIO,Readable):
    
    Status = Enum(
        Drivable.Status,
        DISABLED = StatusType.DISABLED,
        PREPARING = StatusType.PREPARING,
        LOADING=303,
        UNLOADING = 304,
        PAUSED = 305,
        STOPPED = 402,
        LOCAL_CONTROL = 403,
        LOCKED = 404 
        )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status
    
    attached_sample =  Attached(mandatory=True)
    
    attached_robot = Attached(mandatory = True)
    
    storage_size = Parameter("number of slots in storage",
                            datatype=IntRange(),
                            readonly = True,
                            default = 1,
                            visibility ="expert")
       
    
    value = Parameter("Sample objects in storage",
                    datatype=ArrayOf(SchokiStructOf(nsamples),0,nsamples),
                    readonly = True)
    
    last_pos = Parameter("Last loaded or unloaded sample_pos",
             datatype = IntRange(minval= 0,maxval=nsamples),
             default = 1 ,
             readonly = True)
    
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.mag = Magazin(nsamples)
        
    def read_value(self):      
        return self.mag.mag2Arrayof()
    

    def read_status(self):
        robo_stat = self.attached_robot.status
        
        
        
        # Robot Arm is Busy        
        if robo_stat[0] == BUSY:
            if re.match(r'in\d+\.urp',self.attached_robot.value):
                return  LOADING, "Loading sample"
            if re.match(r'out\d+\.urp',self.attached_robot.value):
                return UNLOADING , "Unloading sample"
            
            # Robot Running and No sample in Gripper
            return BUSY , "Robot is in use by another module"
        
        if self.attached_sample._holding_sample():
            return BUSY , "Robot is in use by another module"
        
        
        return robo_stat
    
    def read_last_pos(self):
        return self.last_pos

    
    @Command()
    def stop(self,group = 'control'):
        """Stop execution of program"""
        self.attached_robot.stop()
        return    

    
    @Command(visibility = 'expert',group ='error_handling')
    def reset(self):
        """Reset storage module (removes all samples from storage)"""
        self.mag = Magazin(nsamples)        
        
        
    
    @Command(visibility = 'expert',group ='error_handling')
    def clear_error(self):
        """Trys to clear errors"""
        self.attached_robot.clear_error()
    
    
    @Command(SchokiStructOf(nsamples=nsamples),result=None)
    def load(self,sample_name,substance,substance_code,sample_pos,manufacturer,sample_id,color,mass):
        """load sample into storage"""
     
        
        # check if robot is ready to load sample
        if self.attached_sample._holding_sample():            
            raise ImpossibleError('Gripper is already holding sample: ' + str(self.attached_sample.value))
        
                     
        # check if Sample position is already occupied
        if self.mag.get_sample(sample_pos) != None:
            raise ImpossibleError( "Sample pos "+ str(sample_pos) +" is already occupied")
            
        
        # Run Robot script to insert actual Sample        
        prog_name = 'in'+ str(sample_pos)+ '.urp'
        assert(re.match(r'in\d+\.urp',prog_name))
        
        self.attached_robot.write_target(prog_name)
        
        self.attached_robot.read_status()

        self.read_status()
        
        # Insert new Sample in Storage Array (it is assumed that the robot programm executed successfully)
        new_Sample = Schoki(
            sample_name= sample_name,
            substance= substance,
            samplePos=sample_pos,
            substance_code=substance_code,
            Manufacturer=manufacturer,
            color=color,
            sample_id =sample_id,
            mass=mass) 
        try:
            self.mag.insertSample(new_Sample)
        except:
            raise ImpossibleError( "Sample pos "+ str(sample_pos) +" is already occupied")
            
        
        self.last_pos = sample_pos
        
        return
    
    
    
    @Command(StructOf(substance = EnumType(SCHOKO_SORTEN_ENUM) ,samplepos = IntRange(minval= 1,maxval= nsamples)),result=None)
    def load_short(self,samplepos,substance):
        """load sample into storage"""
        
        # check if robot is ready to load sample
        if self.attached_sample._holding_sample():
            raise ImpossibleError('Gripper is already holding sample' + str(self.attached_sample.value))
        
       
        
        # check if Sample position is already occupied
        if self.mag.get_sample(samplepos) != None:
            raise ImpossibleError( "Sample pos "+ str(samplepos) +" is already occupied")
            

        
        # Run Robot script to insert actual Sample        
        prog_name = 'in'+ str(samplepos)+ '.urp'
        assert(re.match(r'in\d+\.urp',prog_name))
        
        self.attached_robot.write_target(prog_name)

        self.attached_robot.read_status()

        self.read_status()

        
        
        # Insert new Sample in Storage Array (it is assumed that the robot programm executed successfully)
        try:
            self.mag.insertSample(Schoki(substance.name,samplepos))
        except:
            raise ImpossibleError( "Sample Pos "+ str(samplepos) +" is already occupied")
            
        
        self.last_pos = samplepos
        
        return
              
        
    @Command(IntRange(minval=1,maxval=nsamples),result=None)    
    def unload(self,sample_pos):
        """unload sample from storage"""
        
        # check if robot is ready to load sample
        if self.attached_sample._holding_sample() == True:
            raise ImpossibleError('Gripper is already holding sample' + str(self.attached_sample.value)+" try unloading via 'sample' module")
            

        # check if Sample position is already occupied
        if self.mag.get_sample(sample_pos) == None:
            raise ImpossibleError( "No sample present at pos: "+ str(sample_pos) )
        
        # Run Robot script to unload actual Sample        
        prog_name = 'out'+ str(sample_pos) +'.urp'
        assert(re.match(r'out\d+\.urp',prog_name))
        
        self.attached_robot.write_target(prog_name)
        
        self.attached_robot.read_status()

        self.read_status()

        try:
            self.mag.removeSample(sample_pos)
        except:
            raise ImpossibleError( "No sample at array pos " + str(sample_pos))
        
        self.last_pos = sample_pos
        
        return
            

MOUNTING         = Sample.Status.MOUNTING
UNMOUNTING       = Sample.Status.UNMOUNTING
MEASURING        = Sample.Status.MEASURING
HOLDING_SAMPLE   = Sample.Status.HOLDING_SAMPLE
PAUSED_SAMPLE    = Sample.Status.PAUSED
STOPPED_SAMPLE   = Sample.Status.STOPPED


LOADING          = Storage.Status.LOADING
UNLOADING        = Storage.Status.UNLOADING
PAUSED_STORAGE   = Storage.Status.PAUSED
STOPPED_STORAGE  = Storage.Status.STOPPED
LOCAL_CONTROL    = Storage.Status.LOCAL_CONTROL 
LOCKED           = Storage.Status.LOCKED
ERROR            = Storage.Status.ERROR

PREPARING  = Storage.Status.PREPARING
DISABLED   = Storage.Status.DISABLED