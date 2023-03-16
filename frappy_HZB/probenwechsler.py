
from frappy.datatypes import BoolType, EnumType, FloatRange, StringType, TupleOf, ArrayOf,StatusType

from frappy.core import Command, Parameter, Readable, HasIO, StringIO,StructOf, Property, IDLE, BUSY, WARN, ERROR, IntRange, Drivable, nopoll

from frappy_HZB.robo import RobotIO,ROBOT_MODE_ENUM, ROBOT_MODE_STATUS
from frappy.lib.enum import Enum


from frappy.modules import Attached

import re
import time
import urx
import numpy as np
import uuid
import random




SCHOKO_SORTEN = {
    'None':0,
    'Nuss-Splitter':1,
    'Joghurt':2,
    'Nugat':3,
    'Knusperflakes':4,
    'Marzipan':5,
    'Knusperkeks':6,
    'Edel-Vollmilch':7,
    'Mandel':8
}

SCHOKO_SORTEN_ENUM = {
    'Nuss-Splitter':1,
    'Joghurt':2,
    'Nugat':3,
    'Knusperflakes':4,
    'Marzipan':5,
    'Knusperkeks':6,
    'Edel-Vollmilch':7,
    'Mandel':8
}

SCHOKO_FARBE = {
    'None':'None',
    'Nuss-Splitter':'green',
    'Joghurt':'white',
    'Nugat':'dark blue',
    'Knusperflakes':'yellow',
    'Marzipan':'red',
    'Knusperkeks':'brown',
    'Edel-Vollmilch':'blue',
    'Mandel':'dark green'
}

SCHOKO_FARBE_ENUM = {
    'None':0,
    'Nuss-Splitter':1,
    'Joghurt':2,
    'Nugat':3,
    'Knusperflakes':4,
    'Marzipan':5,
    'Knusperkeks':6,
    'Edel-Vollmilch':7,
    'Mandel':8
}

SAMPLE_POS = {
    'empty':0,
    '(1,1)':1,
    '(1,2)':2,
    '(1,3)':3,
    '(2,1)':4,
    '(2,2)':5,
    '(2,3)':6,
    '(3,1)':7,
    '(3,2)':8,
    '(3,3)':9,
    '(4,1)':10,
    '(4,2)':11,
    '(4,3)':12
}
nsamples = 12

sample_datatype = StructOf(
                        type = StringType(),
                        sample_pos =IntRange(minval= 0,maxval=nsamples),                        
                        manufacturer = StringType(),
                        sample_id = StringType(),
                        color = StringType(),
                        weight = FloatRange(minval=0,maxval=1,unit = 'kg')
                        )

class Schoki:
    def __init__(self, type, samplePos, Manufacturer = 'Rittersport' ,weight =0.0167 ) -> None:
        self.type = type
        self.samplePos =samplePos
        self.Manufacturer = Manufacturer
        self.color = SCHOKO_FARBE.get(self.type,None)
        self.uuid = str(uuid.uuid4())
        self.weight = weight
        
                        #datatype=StructOf(
                        #type = EnumType(members=SCHOKO_SORTEN),
                        #sample_pos =IntRange(minval=1,maxval=storage_size.value),                        
                        #manufacturer = StringType(),
                        #sample_id = StringType(),
                        #color = EnumType(members =SCHOKO_FARBE_ENUM)
                        #)
                
    def toStructOf(self):

        return {'type' : self.type,
                'sample_pos':self.samplePos,
                'manufacturer':self.Manufacturer,
                'sample_id':self.uuid,
                'color': self.color,
                'weight':self.weight
                }
        
        
        
class Magazin:
    Mag_dict = {}
    
    def __init__(self,nSamples,magname):
        self.Mag = [None] * nSamples
        Magazin.Mag_dict[magname] = self.Mag
        
               
        
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
    
    Status = Enum(Drivable.Status,IDLE_HOLDING_SAMPLE = 101, MOUNTING=301,UNMOUNTING = 302,MEASURING = 303)  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

    attached_robot = Attached(mandatory = True)
    attached_storage = Attached(mandatory = True)
    
    nsamples = 12 #TODO better solution needed

    
    value = Parameter("Active Sample held by robot arm",
                      datatype=EnumType("active Sample",SAMPLE_POS),
                      readonly = True,
                      default = 'empty') 

    target =  Parameter("Target Sample to be held by robot arm",
                      datatype=EnumType("target Sample",SAMPLE_POS),
                      default = 'empty')
    
    sample_struct = Parameter("Sample Object",
                    datatype=sample_datatype,
                    readonly = True,
                    group = 'sample') 
    
    type = Parameter("Sample type currently held my robot Arm",
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
    weight = Parameter("weight of sample currently held my robot Arm",
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
    

    def read_sample_struct(self):
        if self._holding_sample():
            current_sample = self._get_current_sample()
            return current_sample.toStructOf()
        
        return {'type' : 'none',
                'sample_pos': 0,
                'manufacturer':'none',
                'sample_id':'none',
                'color': 'none',
                'weight':0
                }
    


    
    def read_type(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.type
        return 'none'
    
    def read_color(self):
        if self._holding_sample() :
            sample = self._get_current_sample()
            return sample.color
        return 'none'
    
    def read_sample_id(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.uuid
        return 'none'
   
        
    def read_manufacturer(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.Manufacturer
        return 'none'
    
    def read_weight(self):
        if self._holding_sample():
            sample = self._get_current_sample()
            return sample.weight
        return 0
    
    def _holding_sample(self):
        if self.value.value == 0:
            return False
        return True
        

    def _run_robot_program(self,prog_name):
        self.attached_robot.write_target(prog_name)
        if self.attached_robot.status[0] == ERROR:
            return False
        
        return True
    
    
    def _get_current_sample(self):
        return self.attached_storage.mag.get_sample(self.value)
    
    def write_target(self,target):
        
        # check if robot is currently holding a Sample from Storage
        if self._holding_sample():
            self.status = ERROR, 'Gripper not empty, holding sample: ' + str(self.value)
            return self.target
        
        # check if sample is present in Storage
        if not self.attached_storage.mag.get_sample(target):
            self.status = ERROR, 'no Sample at Pos' +str(target)
            return self.target
        
        return target
    
    

    
    
    def read_status(self):
        robo_stat = self.attached_robot.status
        
        
        # Robot Idle and sample in Gripper
        if robo_stat[0] == IDLE and self._holding_sample():
            
            return IDLE_HOLDING_SAMPLE , "IDLE with Sample in Gripper"
        
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


    
    @Command
    def mount(self):
        """Mount Sample to Robot arm"""
        
        if self.target == 'empty':
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
        prog_name = 'messpos'+ str(self.target.value) + '.urp'
        
        assert(re.match(r'messpos\d+\.urp',prog_name) )
        
        success = self._run_robot_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <mount> Robot Program'
            return
        self.status = 301 , "Mounting Sample"
        # Robot successfully mounted the sample
        self.value = self.target
        
        

    
    @Command
    def unmount(self):
        """Unmount Sample to Robot arm"""
                # check if robot is ready to mount sample
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
        prog_name = 'messposin'+ str(self.target.value) + '.urp'
        
        assert(re.match(r'messposin\d+\.urp',prog_name) )
        
        success = self._run_robot_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <mount> Robot Program'
            return
        
        self.status = 302 , "Unmounting Sample"
        
        # Robot successfully unmounted the sample
        self.value = 'empty'

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
        
  
        
        success = self._run_robot_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <measure> Robot Program'
            return
        
        
        self.status = 303 , "Measuring Sample"
        
    @Command
    def stop(self):
        """Stop execution of program"""
        stop_reply  = str(self.communicate('stop'))
        
        if stop_reply.__eq__('Stopped'):
            self.status = IDLE, "Stopped Execution"
        else:
            self.status = ERROR, "Failed to execute: stop"
        
    # @Command(group = 'admin commands',visibility = 'expert')
    # def force_mount(self):
    #     """unmount Sample to Robot without calling robot program"""
    #     pass
    
    # @Command(group = 'admin commands',visibility = 'expert')
    # def force_unmount(self):
    #     """unmount Sample to Robot without calling robot program"""
    #     pass
    
    
    
    
class Storage(HasIO,Readable):
    
    


    attached_sample =  Attached(mandatory=True)
    
    attached_robot = Attached(mandatory = True)
    
    storage_size = Parameter("number of slots in Storage",
                            datatype=IntRange(),
                            readonly = True,
                            default = 1,
                            visibility ="expert")
    
     
    


    
    
    value = Parameter("Sample objects in Storage",
                    datatype=ArrayOf(sample_datatype,0,nsamples),
                    readonly = True
                )
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.mag = Magazin(nsamples,'Storage')
        
    
    
    def read_value(self):      
        return self.mag.mag2Arrayof()
    


    def read_status(self):
        return  IDLE, ''
    
    def _run_robot_program(self,prog_name):
        self.attached_robot.write_target(prog_name)
        if self.attached_robot.status[0] == ERROR:
            return False
        
        return True
    
    
    @Command(StructOf(type = EnumType(SCHOKO_SORTEN_ENUM) ,samplepos = IntRange(minval= 1,maxval= nsamples)),result=None)
    def load(self,samplepos,type):
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
        success = self._run_robot_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <load> Robot Program'
            return
        
        
        # Insert new Sample in Storage Array (it is assumed that the robot programm executed successfully)
        try:
            self.mag.insertSample(Schoki(type.name,samplepos))
        except:
            self.status = ERROR, "Sample Pos already occupied"
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

        
        # Run Robot script to insert actual Sample        
        prog_name = 'out'+ str(sample_pos) +'.urp'
        assert(re.match(r'out\d+\.urp',prog_name))
        success = self._run_robot_program(prog_name)
        
        # errors while loading robot program
        if not success:
            self.status = ERROR, 'failed to run <unload> Robot Program'
            return
        
        try:
            self.mag.removeSample(sample_pos)
        except:
            self.status = ERROR, "No sample at Pos "
            

MOUNTING = Sample.Status.MOUNTING
UNMOUNTING = Sample.Status.UNMOUNTING
MEASURING = Sample.Status.MEASURING
IDLE_HOLDING_SAMPLE = Sample.Status.IDLE_HOLDING_SAMPLE