Node('SIM_MLZ_amagnet(Garfield)',
    'MLZ-Amagnet\n'
    '\n'
    'Water cooled magnet from ANTARES@MLZ.\n'
    '\n'
    '    Use module to control the magnetic field.\n'
    'Don\'t forget to select symmetry first (can be moved only at zero field!).\n'
    '\n'
    'Monitor T1..T4 (Coil temps), if they get to hot, field will ramp down!\n'
    '\n'
    'In case of Problems, contact the ANTARES people at MLZ.',
    'tcp://10767',
    visibility = 'expert',
    foo = 'bar',
)

Mod('enable',
    'frappy.simulation.SimWritable',
    'Enables to Output of the Powersupply',
    value = Param(datatype={"type":"enum", "members":{'On':1,'Off':0}}),
    target = Param(datatype={"type":"enum", "members":{'On':1,'Off':0}}),
    visibility = 'advanced',
)

Mod('polarity',
    'frappy.simulation.SimWritable',
    'polarity (+/-) switch\n'
    '\n'
    'there is an interlock in the plc:\n'
    'if there is current, switching polarity is forbidden\n'
    'if polarity is short, powersupply is disabled',
    value = Param(datatype={"type":"enum", "members":{'+1':1,'0':0,'-1':-1}}),
    target = Param(datatype={"type":"enum", "members":{'+1':1,'0':0,'-1':-1}}),
    visibility = 'advanced',
)


Mod('symmetry',
    'frappy.simulation.SimWritable',
    'par/ser switch selecting (a)symmetric mode\n'
    '\n'
    'note: on the front panel symmetric is ser, asymmetric is par',
    value = Param(
        datatype={"type":"enum", "members":{'symmetric':1,'short':0, 'asymmetric':-1}},
        default = 'symmetric'
        ),
    target = Param(datatype={"type":"enum", "members":{'symmetric':1,'short':0, 'asymmetric':-1}}),
    visibility = 'advanced',
)

for i in range(1,5):
    Mod('T%d' % i,
        'frappy.simulation.SimReadable',
        'Temperature%d of the coils system' % i,
        value = Param(default = 23.45, unit='degC'),
    )

Mod('currentsource',
    'frappy.simulation.SimDrivable',
    'Device for the magnet power supply (current mode)',
    value = 0,
    #abslimits = (0,200),
    #speed = 1,
    #ramp = 60,
    #precision = 0.02,
    #current = 0,
    #voltage = 10,
    visibility = 'advanced',
    extra_params = 'abslimits, speed, ramp, precision, current, voltage, window',
    abslimits = Param(
        default = (0, 200),
        datatype = {"type":"limit", "members":{"type":"double", "min":0, "max":200, "unit":"A"}}
    ),
    speed = Param(
        default = 10,
        datatype = {"type":"double", "min":0, "max":10, "unit":"A/s"}
        ),
    ramp = Param(
        default = 600,
        datatype = {"type":"double", "min":0, "max":600, "unit":"A/min"}
        ),
    precision = Param(
        default = 0.1,
        datatype = {"type":"double", "unit":"A"}
        ),
    current = Param(
        default = 0,
        datatype = {"type":"double", "min":0, "max":200, "unit":"A"}
        ),
    voltage = Param(
        default = 0,
        datatype = {"type":"double", "min":0, "max":10, "unit":"V"}
        ),
    window = Param(
        default = 10,
        datatype = {"type":"double", "min":0, "max":120, "unit":"s"}
    )
)

Mod('mf',
    'frappy_mlz.amagnet.GarfieldMagnet',
    'magnetic field module, handling polarity switching and stuff',
    currentsource='currentsource',
    enable='enable',
    polswitch='polarity',
    symmetry='symmetry',
    target = Param(unit='T'),
    value = Param(unit='T'),
    userlimits=(-0.35, 0.35),
    calibrationtable={'symmetric':[0.00186517, 0.0431937, -0.185956, 0.0599757, 0.194042],
        'short': [0.0, 0.0, 0.0, 0.0, 0.0],
        'asymmetric':[0.00136154, 0.027454, -0.120951, 0.0495289, 0.110689]},
    meaning=("magneticfield", 20),
    visibility='user',
    abslimits=(-0.4,0.4),
)
