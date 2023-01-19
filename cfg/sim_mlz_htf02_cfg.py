Node('htf02',
    '[sim] htf02 box of MLZ Sample environment group\n'
    '\n'
    'Controls an High Temperature Furnace with an eurotherm controller and an PLC checking the cooing water.',
    'tcp://10767',
)

Mod('T_htf02',
    'frappy.simulation.SimDrivable',
    'Main temperature control node of htf02.\n'
    '\n'
    'Controls the regulation loop of the Eurotherm.',
    value = Param(default=300,
        datatype={"type":"double", "min":0, "unit":"degC"}),
    target = Param(default=300,
        datatype={"type":"double", "min":0, "max": 2000, "unit":"degC"}),
    extra_params='ramp',
    ramp = Param(default=60,
        datatype={"type":"double", "min":0, "max": 600, "unit":"K/min"},
        description='target ramping speed in K/min.',
        readonly=False,
    ),
    meaning=["temperature", 10],
)

Mod('htf02_p',
    'frappy.simulation.SimReadable',
    'Pressure Sensor at sample space (ivc).',
    value = Param(default=989, datatype={"type":"double", "min":0, "unit":"mbar"}),
)
