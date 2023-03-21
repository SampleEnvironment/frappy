Node('cci3he1',
    '[sim] cci3he box of MLZ Sample environment group\n'
    '\n'
    'Controls an 3He insert with an ls370 and an PLC controlling \n'
    'the compressor and the valves of the gas handling.',
    'tcp://10767',
)

Mod('T_cci3he1',
    'frappy.simulation.SimDrivable',
    'Main temperature control node of cci3he1.\n'
    '\n'
    'Controls the regulation loop of the ls370.',
    value = Param(default=300, datatype={"type":"double","unit":"K"}),
    target = Param(default=300, datatype={"type":"double", "min":0, "max":300, "unit":"K"}),
    extra_params='ramp',
    ramp = Param(default=60,
        datatype={"type":"double","min":0,"max":600,"unit":"K/min"},
        description='target ramping speed in K/min.',
    ),
    meaning=["temperature_regulation",40]
)

Mod('T_cci3he1_A',
    'frappy.simulation.SimReadable',
    '3He pot temperature sensor. Also used for the regulation.',
    visibility='expert',
    value = Param(default=300, datatype={"type":"double","unit":"K"}),
    meaning=["temperature",38]
)

Mod('T_cci3he1_B',
    'frappy.simulation.SimReadable',
    '(optional) sample temperature sensor close to sample.',
    visibility='user',
    value = Param(default=300, datatype={"type":"double","unit":"K"}),
    meaning=["temperature",39]
)

Mod('cci3he1_p1',
    'frappy.simulation.SimReadable',
    'Pressure at turbo pump inlet.',
    value = Param(default=2e-3, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_p2',
    'frappy.simulation.SimReadable',
    'Pressure at turbo pump outlet.',
    value = Param(default=9.87, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_p3',
    'frappy.simulation.SimReadable',
    'Pressure at compressor inlet.',
    value = Param(default=19.99, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_p4',
    'frappy.simulation.SimReadable',
    'Pressure at compressor outlet.',
    value = Param(default=999, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_p5',
    'frappy.simulation.SimReadable',
    'Pressure in dump tank.',
    value = Param(default=567, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_p6',
    'frappy.simulation.SimReadable',
    'Pressure in the vacuum dewar (ivc).',
    value = Param(default=1e-3, datatype={"type":"double","unit":"mbar"}),
    visibility='expert',
)

Mod('cci3he1_flow',
    'frappy.simulation.SimReadable',
    'Gas Flow (condensing line).',
    value = Param(default=12.34, datatype={"type":"double","unit":"mln/min"}),
    visibility='expert',
)
# note: all valves and switches are missing: use VNC to control them
