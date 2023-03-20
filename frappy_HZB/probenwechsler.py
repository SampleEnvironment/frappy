
from frappy.datatypes import  EnumType, FloatRange, StringType, ArrayOf,StatusType

from frappy.core import Command, Parameter, Readable, HasIO,StructOf, IDLE, BUSY, ERROR, IntRange, Drivable


from frappy.lib.enum import Enum


from frappy.modules import Attached

import re
import uuid

from frappy.properties import Property

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






#TODO reset Command Sample
#TODO reset Command Storage

#TODO clear_error Command Sample
#TODO clear_error Command Storage
#TODO reset.urp Program

#TODO describe None {...} -->  describe . {...}

class SchokiStructOf(StructOf):
    def __init__(self, nsamples):
        super().__init__( 
                        substance = StringType(),
                        substance_code = StringType(),
                        sample_pos =IntRange(minval= 0,maxval=nsamples),                        
                        manufacturer = StringType(),
                        sample_id = StringType(),
                        color = StringType(),
                        mass = FloatRange(minval=0,maxval=1,unit = 'kg')
                        )

class Schoki:
    def __init__(self, substance,samplePos, substance_code = None, Manufacturer = None ,color = None,sample_id = None,mass =None ) -> None:
        self.substance = substance
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
                
    def toStructOf(self):

        return {'substance' : self.substance,
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
                  HOLDING_SAMPLE = 101, 
                  MOUNTING=301,
                  UNMOUNTING = 302,
                  MEASURING = 303,
                  PAUSED = 304,
                  STOPPED = 402
                  )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    attached_robot = Attached(mandatory = True)
    attached_storage = Attached(mandatory = True)
    

    
    value = Parameter("Active Sample held by robot arm",
                      datatype=IntRange(minval=0,maxval=nsamples),
                      readonly = True,
                      default = 0) 

    target =  Parameter("Target Sample to be held by robot arm",
                      datatype=IntRange(minval=0,maxval=nsamples),
                      default = 0)
    
    sample_struct = Parameter("Sample Object",
                    datatype=SchokiStructOf(nsamples),
                    readonly = True,
                    group = 'sample') 
    
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
    color = Parameter("color of sample currently held my robot Arm",
                     datatype=StringType(),
                     default = 'none',
                     readonly= True,
                     group = 'sample')
    mass = Parameter("mass of sample currently held my robot Arm",
                     datatype=FloatRange(minval=0,maxval=1,unit = 'kg'),
                     default = 0,
                     readonly= True,
                     group = 'sample')
    
    
    def doPoll(self):
        self.read_value()
        self.read_status()

    def read_value(self):
        return self.value
        
    
    def read_target(self):
        return self.target
    
    def write_target(self,target):
        
        # check if robot is currently holding a Sample from Storage
        if self._holding_sample() and target != 0:
            self.status = ERROR, 'Gripper not empty, holding sample: ' + str(self.value)
            return self.target
        
        # check if sample is present in Storage
        if not self.attached_storage.mag.get_sample(target) and target != 0:
            self.status = ERROR, 'no Sample at Pos' +str(target)
            return self.target
        
        self.target = target
        
        ### Mount:
        if target != 0:
            self._mount()
        ### Unmount:
        if target == 0:
            self._unmount()
            
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
            
            # Robot Running and No sample in Gripper
            return BUSY , "Robot is in use by other module"
        
        return robo_stat
    

    def read_sample_struct(self):
        if self._holding_sample():
            current_sample = self._get_current_sample()
            return current_sample.toStructOf()
        
        return {'substance' : 'none',
                'substance_code':'none',
                'sample_pos': 0,
                'manufacturer':'none',
                'sample_id':'none',
                'color': 'none',
                'mass':0
                }
    
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
        
    
    def _mount(self):
        """Mount Sample to Robot arm"""
        
        if self.target == 0:
            self.status = ERROR, 'not a valid Target'
            return 
        
        # check if robot is ready to mount sample
        if self._holding_sample():
            self.status = ERROR, 'Gripper already holding Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'  
            return
        
        # check if Sample is present in Storage
        if self._get_current_sample == None :
            self.status = ERROR, "Sample Pos "+ str(self.value) +" does not contain a sample"
            return

        
        # Run Robot script to mount actual Sample        
        prog_name = 'messpos'+ str(self.target) + '.urp'
        
        assert(re.match(r'messpos\d+\.urp',prog_name) )
        
        success =  self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <mount> Robot Program'
            return
        self.status = 301 , "Mounting Sample"
        # Robot successfully mounted the sample
        self.value = self.target
     

    def _unmount(self):
        """Unmount Sample to Robot arm"""
                # check if robot is ready to mount sample
        if not self._holding_sample():
            self.status = ERROR, 'Gripper is currently not holding a Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'  
            return
        
        # check if Sample slot is is present in Storage
        if self._get_current_sample == None :
            self.status = ERROR, "Sample Pos "+ str(self.value) +" does not contain a sample"
            return

        
        # Run Robot script to unmount Sample        
        prog_name = 'messposin'+ str(self.value) + '.urp'
        
        assert(re.match(r'messposin\d+\.urp',prog_name) )
        
        success =  self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <mount> Robot Program'
            return
        
        self.status = 302 , "Unmounting Sample"
        
        # Robot successfully unmounted the sample
        self.value = 0

    @Command
    def measure(self):
        """Measure Sample held by Robot arm"""

        # check if robot is holding a sample
        if not self._holding_sample():
            self.status = ERROR, 'Gripper is currently not holding a Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'  
            return
        
        # check if Sample is present in Storage
        if self._get_current_sample == None :
            self.status = ERROR, "Sample Pos "+ str(self.value) +" does not contain a sample"
            return

        
        # Run Robot script to unmount Sample        
        prog_name = 'messen.urp'
        
  
        
        success =  self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <measure> Robot Program'
            return
        
        
        self.status = 303 , "Measuring Sample"
        
    @Command
    def stop(self):
        """Stop execution of program"""
        self.attached_robot.stop()

        
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
        LOADING=301,
        UNLOADING = 302,
        PAUSED = 304,
        STOPPED = 402
        )  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status
    
    attached_sample =  Attached(mandatory=True)
    
    attached_robot = Attached(mandatory = True)
    
    storage_size = Parameter("number of slots in Storage",
                            datatype=IntRange(),
                            readonly = True,
                            default = 1,
                            visibility ="expert")
       
    
    value = Parameter("Sample objects in Storage",
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
                return  LOADING, "Loading Sample"
            if re.match(r'out\d+\.urp',self.attached_robot.value):
                return UNLOADING , "Unloading Sample"
            
            # Robot Running and No sample in Gripper
            return BUSY , "Robot is in use by other module"
        
        return robo_stat
    
    @Command()
    def stop(self):
        """Stop execution of program"""
        self.attached_robot.stop()
        return    

    
    @Command(SchokiStructOf(nsamples=nsamples),result=None)
    def load(self,substance,substance_code,sample_pos,manufacturer,sample_id,color,mass):
        """load sample into storage"""
        
        # check if robot is ready to load sample
        if self.attached_sample._holding_sample():
            self.status = ERROR, 'Gripper already holding Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'  
            return
        
               
        # check if Sample position is already occupied
        if self.mag.get_sample(sample_pos) != None:
            self.status = ERROR, "Sample Pos "+ str(sample_pos) +" already occupied"
            return

        
        # Run Robot script to insert actual Sample        
        prog_name = 'in'+ str(sample_pos)+ '.urp'
        assert(re.match(r'in\d+\.urp',prog_name))
        success =  self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <load> Robot Program'
            return
        
        
        # Insert new Sample in Storage Array (it is assumed that the robot programm executed successfully)
        new_Sample = Schoki(
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
            self.status = ERROR, "Sample Pos already occupied in Magazin Array"
            return
        
        self.last_pos = sample_pos
        
        return
    
    
    
    @Command(StructOf(substance = EnumType(SCHOKO_SORTEN_ENUM) ,samplepos = IntRange(minval= 1,maxval= nsamples)),result=None)
    def load_short(self,samplepos,substance):
        """load sample into storage"""
        
        # check if robot is ready to load sample
        if self.attached_sample._holding_sample():
            self.status = ERROR, 'Gripper already holding Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'  
            return
        
        
        
        # check if Sample position is already occupied
        if self.mag.get_sample(samplepos) != None:
            self.status = ERROR, "Sample Pos "+ str(samplepos) +" already occupied"
            return

        
        # Run Robot script to insert actual Sample        
        prog_name = 'in'+ str(samplepos)+ '.urp'
        assert(re.match(r'in\d+\.urp',prog_name))
        success =  self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <load> Robot Program'
            return
        
        
        # Insert new Sample in Storage Array (it is assumed that the robot programm executed successfully)

        try:
            self.mag.insertSample(Schoki(substance.name,samplepos))
        except:
            self.status = ERROR, "Sample Pos already occupied in Magazin Array"
            return
        
        self.last_pos = samplepos
        
        return
              
        
    @Command(IntRange(minval=1,maxval=nsamples),result=None)    
    def unload(self,sample_pos):
        """unload sample from storage"""
        
               # check if robot is ready to load sample
        if self.attached_sample._holding_sample() == True:
            self.status = ERROR, 'Gripper already holding Sample'
            return
        
        if self.attached_robot.status[0] != IDLE:
            self.status = ERROR, 'Robot Arm is not ready to be used'   
            return
        
        # check if Sample position is already occupied
        if self.mag.get_sample(sample_pos) == None:
            self.status = ERROR, "No sample present at pos: "+ str(sample_pos) 
            return

        
        # Run Robot script to unload actual Sample        
        prog_name = 'out'+ str(sample_pos) +'.urp'
        assert(re.match(r'out\d+\.urp',prog_name))
        success = self.attached_robot.run_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <unload> Robot Program'
            return
        
        

        try:
            self.mag.removeSample(sample_pos)
        except:
            self.status = ERROR, "No sample at Array Pos " + str(sample_pos)
            return
        
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


