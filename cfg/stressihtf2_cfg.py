Node('stressihtf2',
    'Stressihtf2 box of MLZ Sample environment group\n'
    '\n'
    'Controls an High Temperature Furnace with an Eurotherm and an PLC controlling some valves and checking cooling water.',
     'localhost:10767',
    meaning={'T_regulation':{'T':100}, 'T_sample':{'T_sample':100}},
)


Mod('T',
    'frappy_mlz.entangle.TemperatureController',
    'Main temperature control node of Stressihtf2.',
    tangodevice='tango://localhost:10000/box/eurotherm/ctrl',
    value = Param(unit='degC'),
    target = Param(datatype=["double", 0, 2000]),
    ramp = Param(
        default=60,
        datatype=["double",0,9999],
        unit='K/min',
        description='target ramping speed in K/min.',
    ),
    abslimits = Param(
        default=[0,2000],
        datatype=["tuple",[["double"],["double"]]],
        unit='degC',
        description='currently active absolute limits for the setpoint.\
                depend on the regulationmode parameter (both/stick->0..600, tube->0..300K).',
        readonly=True,
    ),
    userlimits = Param(
        default=[0,300],
        datatype=["tuple",[["double"],["double"]]],
        unit='degC',
        description='current user set limits for the setpoint. must be inside abslimits.',
    ),
    heateroutput = Param(
        default=0,
        datatype=["double",0,100],
        unit='%%',
        description='output to the heater',
    ),
    setpoint = 0,
    p = 1,
    i = 0,
    d = 0,
    pid = [1,0,0],
    speed = 0,
)

Mod('T_sample_a',
    'frappy_mlz.entangle.Sensor',
    'Regulation temperature sensor.',
    tangodevice='tango://localhost:10000/box/eurotherm/sensora',
    value = Param(unit='degC'),
    visibility='user',
)

Mod('T_sample_b',
    'frappy_mlz.entangle.Sensor',
    '(optional) Sample temperature sensor.',
    tangodevice='tango://localhost:10000/box/eurotherm/sensorb',
    value = Param(unit='degC'),
    visibility='expert',
)

Mod('N2',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'Switches the N2 gas inlet on or off.',
    tangodevice='tango://localhost:10000/box/plc/_gas1',
    mapping={'off':0,'on':1},
    visibility='expert',
)

Mod('He',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'Switches the He gas inlet on or off.',
    tangodevice='tango://localhost:10000/box/plc/_gas2',
    mapping={'off':0,'on':1},
    visibility='expert',
)

Mod('lamps',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'Switches the heating lamps on or off.',
    tangodevice='tango://localhost:10000/box/plc/_onoff',
    mapping={'off':0,'on':1},
    visibility='expert',
)

Mod('water_ok',
    'frappy_mlz.entangle.NamedDigitalInput',
    'Readout of the cooling water state.',
    tangodevice='tango://localhost:10000/box/plc/_waterok',
    mapping={'failed':0,'ok':1},
    visibility='expert',
)
