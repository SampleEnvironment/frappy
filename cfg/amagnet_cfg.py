Node('MLZ_amagnet(Garfield)',
    'MLZ-Amagnet\n'
    '\n'
    'Water cooled magnet from ANTARES@MLZ.\n'
    '\n'
    'Use module to control the magnetic field.\n'
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
    'frappy_mlz.entangle.NamedDigitalOutput',
    'Enables to Output of the Powersupply',
    tangodevice = 'tango://localhost:10000/box/plc/_enable',
    value = Param(datatype=["enum", {'On':1,'Off':0}]),
    target = Param(datatype=["enum", {'On':1,'Off':0}]),
    visibility = 'advanced',
)

Mod('polarity',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'polarity (+/-) switch\n'
    '\n'
    'there is an interlock in the plc:\n'
    'if there is current, switching polarity is forbidden\n'
    'if polarity is short, powersupply is disabled',
    tangodevice = 'tango://localhost:10000/box/plc/_polarity',
    value = Param(datatype=["enum", {'+1':1,'0':0,'-1':-1}]),
    target = Param(datatype=["enum", {'+1':1,'0':0,'-1':-1}]),
    visibility = 'advanced',
    comtries = 50,
)

Mod('symmetry',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'par/ser switch selecting (a)symmetric mode\n'
    '\n'
    'symmetric is ser, asymmetric is par',
    tangodevice = 'tango://localhost:10000/box/plc/_symmetric',
    value = Param(datatype=["enum",{'symmetric':1,'short':0, 'asymmetric':-1}]),
    target = Param(datatype=["enum",{'symmetric':1,'short':0, 'asymmetric':-1}]),
    visibility = 'advanced',
)

for i in range(1,5):
    Mod('T%d' % i,
        'frappy_mlz.entangle.AnalogInput',
        'Temperature %d of the coils system' % i,
        tangodevice = 'tango://localhost:10000/box/plc/_t%d' % i,
        #warnlimits=(0, 50),
        value = Param(unit='degC'),
    )

Mod('currentsource',
    'frappy_mlz.entangle.PowerSupply',
    'Device for the magnet power supply (current mode)',
    tangodevice = 'tango://localhost:10000/box/lambda/curr',
    abslimits = (0,200),
    speed = 1,
    ramp = 60,
    precision = 0.02,
    current = 0,
    voltage = 10,
    #value=Param(unit='A')
    visibility = 'advanced',
)

Mod('mf',
    'frappy_mlz.amagnet.GarfieldMagnet',
    'magnetic field module, handling polarity switching and stuff',
    subdev_currentsource = 'currentsource',
    subdev_enable = 'enable',
    subdev_polswitch = 'polarity',
    subdev_symmetry = 'symmetry',
    target = Param(unit='T'),
    value = Param(unit='T'),
    userlimits = (-0.35, 0.35),
    calibrationtable = {'symmetric':[0.00186517, 0.0431937, -0.185956, 0.0599757, 0.194042],
    'short': [0.0, 0.0, 0.0, 0.0, 0.0],
    'asymmetric':[0.00136154, 0.027454, -0.120951, 0.0495289, 0.110689]},
    meaning = ['The magnetic field', 1],
    #priority=100,
    visibility = 'user',
    abslimits = (-0.4,0.4,),
)
