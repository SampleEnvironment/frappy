nsamples = 12

Node('sample_changer.HZB',  # a globally unique identification
     'Sample Changer\n\nThis is an demo for a  SECoP (Sample Environment Communication Protocol) sample changer SEC-Node.',  # describes the node
      'tcp://10770',
      implementor = 'Peter Wegmann')  # you might choose any port number > 1024
Mod('io',  # the name of the module
    'frappy_HZB.robo.RobotIO',  # the class used for communication
    'TCP communication to robot Dashboard Server Interface',  # a description
    uri='tcp://localhost:29999',  # the serial connection
)    
    
Mod('robot',
    'frappy_HZB.robo.UR_Robot',
    'Module for controlling the Robotarm. It provides diagnostic information on the tool center point, joint information and general status of the robot',
    io='io',
    attached_sample = 'sample',
    attached_storage = 'storage',
    group = 'UR_Robot',
    
    
    model = "none",
    serial = "none",
    ur_version = "none",
    
    tcp_position = [0,0,0],
    tcp_orientation = [0,0,0],
    joint_temperature = [0,0,0,0,0,0],
    joint_voltage = [0,0,0,0,0,0],
    joint_current = [0,0,0,0,0,0],
    robot_voltage = 0,
    robot_current = 0,
    pollinterval = 0.1,
    stop_State = {'stopped' : False,'interrupted_prog' : 'none'},
    pause_State = {'paused' : False,'interrupted_prog' : 'none'}

)

Mod('storage',
    'frappy_HZB.probenwechsler.Storage',
    'Samplestorage with slots for holding samples',
    io ='io',
    attached_sample = 'sample',
    attached_robot = 'robot',
    group = 'sample_changer',
    storage_size = nsamples,
    pollinterval = 1
  
)

Mod('sample',
    'frappy_HZB.probenwechsler.Sample',
    'Active Sample held by Robot',
    io ='io',
    attached_robot = 'robot',
    attached_storage = 'storage',
    group = 'sample_changer',
    pollinterval = 1
    )



