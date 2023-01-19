Node('ccidu1',
    '[sim] ccidu box of MLZ Sample environment group\n'
    '\n'
    'Controls an 3He/4He dilution insert with an ls372 and an PLC controlling\n'
    'the compressor and the valves of the gas handling.',
    'tcp://10767',
)

Mod('T_ccidu1',
    'frappy.simulation.SimDrivable',
    'Main temperature control node of ccidu1.\n'
    '\n'
    'Controls the regulation loop of the ls372.',
    value = Param(default=300, unit='K'),
    target = Param(default=300, datatype={"type":"double", "min":0, "max":300, "unit":"K"}),
    extra_params='ramp',
    ramp = Param(default=60,
        datatype={"type":"double", "min":0, "max":600, "unit":"K/min"},
        description='target ramping speed in K/min.',
    ),
    meaning=["temperature_regulation",40]
)

Mod('T_ccidu1_A',
    'frappy.simulation.SimReadable',
    'mixing chamber temperature sensor. Also used for the regulation.',
    value = Param(default=300, datatype={"type":"double", "unit":"K"}),
    visibility='expert',
    meaning=["temperature",38],
)

Mod('T_ccidu1_B',
    'frappy.simulation.SimReadable',
    '(optional) sample temperature sensor close to sample.',
    value = Param(default=300, datatype={"type":"double", "unit":"K"}),
    visibility='user',
    meaning=["temperature",39],
)

Mod('ccidu1_pstill',
    'frappy.simulation.SimReadable',
    'Pressure at the still/turbo pump inlet.',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_pinlet',
    'frappy.simulation.SimReadable',
    'Pressure at forepump inlet/turbo pump outlet.',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_poutlet',
    'frappy.simulation.SimReadable',
    'Pressure at forepump outlet/compressor inlet.',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_pkond',
    'frappy.simulation.SimReadable',
    'Pressure at condensing line/compressor outlet.',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_ptank',
    'frappy.simulation.SimReadable',
    'Pressure in dump tank.',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_pvac',
    'frappy.simulation.SimReadable',
    'Pressure in the vacuum dewar (ivc).',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

Mod('ccidu1_flow',
    'frappy.simulation.SimReadable',
    'Gas Flow (condensing line).',
    value = Param(default=999, datatype={"type":"double", "unit":"mbar"}),
    visibility='expert',
)

# note: all valves and switches are missing: use VNC to control them
Mod('ccidu1_V6',
    'frappy.simulation.SimDrivable',
    'Needle valve',
    value = Param(default=99, datatype={"type":"double", "min":0, "max":100, "unit":"%%"}),
    visibility='expert',
)

Mod('ccidu1_V3',
    'frappy.simulation.SimWritable',
    'Dump Valve',
    value = Param(
        default="OFF",
        datatype={"type":"enum", "members":{"on": 1, "OFF":0}}
    ),
    target = Param(datatype={"type":"enum", "members":{"on": 1, "OFF":0}}),
    visibility='expert',
)
