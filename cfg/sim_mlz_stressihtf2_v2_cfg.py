Node('stressihtf2_v2',
    '[sim] Stressihtf2 box of MLZ Sample environment group\n'
    '\n'
    'Controls an High Temperature Furnace with an Eurotherm and an PLC controlling some valves and checking cooling water.',
    'tcp://10767',
)


Mod('T',
    'frappy.simulation.SimDrivable',
    'Main temperature control node of Stressihtf2.',
    value = Param(default=20,
                datatype={"type":"double", "min":0, "unit":"degC"}),
    target = Param(default=20,
                datatype={"type":"double", "min":0, "max":2000, "unit":"degC"}),
    extra_params='ramp,regulationmode,abslimits,userlimits',
    ramp = Param(
        default=60,
        datatype={"type":"double", "min":0, "max":600, "unit":"K/min"},
        description='target ramping speed in K/min.',
    ),
    abslimits = Param(
        default=[0,2000],
        datatype={"type":"limit", "members":{"type":"double", "min":0, "max":2000, "unit":"degC"}},
        description='currently active absolute limits for the setpoint. depend \
                on the regulationmode parameter (both/stick->0..600, tube->0..300K).',
    ),
    userlimits = Param(
        default=[0,300],
        datatype={"type":"limit", "members":{"type":"double", "min":0, "max":2000, "unit":"degC"}},
        description='current user set limits for the setpoint. must be inside abslimits.',
        readonly=False,
    ),
    meaning=['temperature_regulation', 10],
)

Mod('T_sample',
    'frappy.simulation.SimReadable',
    '(optional) Sample temperature sensor.',
    value = Param(default=300,
                datatype={"type":"double", "min":0, "unit":"degC"}),
    visibility='expert',
    meaning=["temperature", 9],
)

Mod('N2',
    'frappy.simulation.SimWritable',
    'Switches the N2 gas inlet on or off.',
    value = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    visibility='expert',
)

Mod('He',
    'frappy.simulation.SimWritable',
    'Switches the He gas inlet on or off.',
    value = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    visibility='expert',
)

Mod('lamps',
    'frappy.simulation.SimWritable',
    'Switches the heating lamps on or off.',
    value = Param(default='on',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(default='on',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    visibility='expert',
)

Mod('water_ok',
    'frappy.simulation.SimReadable',
    'Readout of the cooling water state.',
    value = Param(default='ok',
                datatype={"type":"enum", "members":{'failed':0,'ok':1}}),
    visibility='expert',
)
