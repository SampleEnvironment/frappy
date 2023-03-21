# pylint: skip-file
Node('ccr12',
    '[sim] CCR12 box of MLZ Sample environment group'
    ''
    'Contains a Lakeshore 336 and an PLC controlling the compressor'
    'and some valves.'
    ''
    'This is an improved version, how we think it should be.',
    'tcp://10767',
)

Mod('T_ccr12',
    'frappy.simulation.SimDrivable',
    'Main temperature control node of CCR12.'
    ''
    'Switches between regulation on stick and regulation on tube depending on temperature requested.'
    'May also pump gas for higher temperatures, if configured.'
    'Manual switching of the regulation node is supported via the regulationmode parameter.',
    value = Param(default=300,
                datatype={"type":"double", "min":0, "max":600, "unit":"K"}),
    target = Param(default=300,
                datatype={"type":"double", "min":0, "max":600, "unit":"K"}),
    extra_params='ramp,regulationmode,abslimits,userlimits',
    ramp = Param(
        default=60,
        datatype={"type":"double", "min":0, "max":60, "unit":"K/min"},
        description='target ramping speed in K/min.',
        readonly=False,
    ),
    regulationmode = Param(
        default='both',
        datatype={"type":"enum","members":{"stick":1,"tube":2,"both":3}},
        description='regulate only stick, tube or select based upon the target value.',
        readonly=False,
    ),
    abslimits = Param(
        default=[0,600],
        datatype={"type":"limit","members":{"type":"double", "min":0,"max":600, "unit":"K"}},
        description='currently active absolute limits for the setpoint. depend on the regulationmode parameter (both/stick->0..600, tube->0..300K).',
    ),
    userlimits = Param(
        default=[0,300],
        datatype={"type":"limit","members":{"type":"double", "min":0,"max":600, "unit":"K"}},
        description='current user set limits for the setpoint. must be inside abslimits.',
        readonly=False,
    ),
    meaning=["temperature_regulation", 20],
)

Mod('T_ccr12_A',
    'frappy.simulation.SimReadable',
    '(optional) Sample temperature sensor.',
    value = Param(default=300,
                datatype={"type":"double", "min":0, "unit":"K"}),
    visibility='expert',
    meaning=["temperature", 9],
)

Mod('T_ccr12_B',
    'frappy.simulation.SimReadable',
    '(regulation) temperature sensor on stick.',
    value = Param(default=300, datatype={"type":"double", "min":0, "unit":"K"}),
    visibility='expert',
    meaning=["temperature", 10],
)

Mod('T_ccr12_C',
    'frappy.simulation.SimReadable',
    'Temperature at the coldhead.',
    value = Param(default=70, datatype={"type":"double", "min":0, "unit":"K"}),
    visibility='expert',
    meaning=["temperature", 1],
)

Mod('T_ccr12_D',
    'frappy.simulation.SimReadable',
    '(regulation) temperature at coupling to stick.',
    value = Param(default=80, datatype={"type":"double", "min":0, "unit":"K"}),
    visibility='expert',
    meaning=["temperature", 2],
)

Mod('ccr12_pressure_regulation',
    'frappy.simulation.SimReadable',
    'Simple two-point presssure regulation. the mode parameter selects the readout on which to regulate, or, \'none\' for no regulation.',
    value = Param(default = 1e-5,
                datatype={"type":"double", "min":0, "max":1000, "unit":"mbar"}),
    extra_params='switchpoints, mode',
    mode = Param(
        default='none',
        datatype={"type":"enum", "members":{"none":0,"p1":1,"p2":2}},
        description='Select pressure sensor to regulate on, or \'none\' to disable regulation.',
    ),
    switchpoints = Param(
        default={'lower':1e-6,'upper':1e-3},
        # struct is more explicit, but ugly to read....
        datatype={"type":"struct", "members":{"lower":{"type":"double", "unit":"mbar"},"upper":{"type":"double", "unit":"mbar"}}, "optional":["upper","lower"]},
        description='Switching points for regulation. If the selected pressure is below \'lower\' value, the gas valve is opened, above \'upper\' the value vacuum valve is openend, else both are closed. values for switchpoints are taken from the selected pressure sensors userlimits.',
        readonly=True,
    ),
    visibility='user',
)

Mod('ccr12_compressor',
    'frappy.simulation.SimDrivable',
    'Switches the compressor for the cooling stage on or off.\n'
    '\n'
    'Note: This should always be on, except for fast heatup for sample change.',
    value = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(datatype={"type":"enum", "members":{'off':0,'on':1}}),
    visibility='user',
)

Mod('ccr12_gas_switch',
    'frappy.simulation.SimWritable',
    'Switches the gas inlet on or off.\n'
    '\n'
    'note: in reality this switches itself off after 15min.\n'
    'note: in reality this is interlocked with ccr12_vacuum_switch, only one can be on!\n'
    'note: in this simulation this module is isolated.',
    value = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
)

Mod('ccr12_vacuum_switch',
    'frappy.simulation.SimWritable',
    'Switches the vacuum pumping valve on or off.\n'
    '\n'
    'note: in reality this is interlocked with ccr12_gas_switch, only one can be on!\n'
    'note: in this simulation this module is isolated.',
    value = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
    target = Param(default='off',
                datatype={"type":"enum", "members":{'off':0,'on':1}}),
)

Mod('ccr12_p1',
    'frappy.simulation.SimReadable',
    'Default pressure Sensor, linear scale 0..1000 mbar\n'
    '\n'
    'Good candidate for a \'Sensor\' Interface class!',
    value = Param(default=999, unit='mbar'),
    extra_params='curve, userlimits',
    curve = Param(
        default='TTR100',
        datatype={"type":"enum", "members":{'0..10V':0,'default':1,'0..9V':2,'DI200':3,'DI2000':4,'TTR100':7,'PTR90':8,'PTR225/PTR237':9,'ITR90':10,'ITR100 curve D':11, 'ITR100 curve 2':12, 'ITR100 curve 3':13,'ITR100 curve 4':14,'ITR100 curve 5':15, 'ITR100 curve 6':16, 'ITR100 curve 7':17, 'ITR100 curve 8':18, 'ITR100 curve 9':19, 'ITR100 curve A':20,'CMR361':21, 'CMR362':22, 'CMR363':23, 'CMR364':24, 'CMR365':25}},
        description='Calibration curve for pressure sensor',
    ),
    userlimits = Param(
        default=[1, 100],
        datatype={"type":"limit","members":{"type":"double", "min":0,"max":1000, "unit":"mbar"}},
        description='current user set limits for the pressure regulation.',
        readonly=False,
    ),
)

Mod('ccr12_p2',
    'frappy.simulation.SimReadable',
    'Auxillary pressure Sensor.',
    value = Param(default=1e-6, unit='mbar'),
    extra_params='curve,userlimits',
    curve = Param(
        default='PTR90',
        datatype={"type":"enum", "members":{'0..10V':0,'default':1,'0..9V':2,'DI200':3,'DI2000':4,'TTR100':7,'PTR90':8,'PTR225/PTR237':9,'ITR90':10,'ITR100 curve D':11, 'ITR100 curve 2':12, 'ITR100 curve 3':13,'ITR100 curve 4':14,'ITR100 curve 5':15, 'ITR100 curve 6':16, 'ITR100 curve 7':17, 'ITR100 curve 8':18, 'ITR100 curve 9':19, 'ITR100 curve A':20,'CMR361':21, 'CMR362':22, 'CMR363':23, 'CMR364':24, 'CMR365':25}},
        description='Calibration curve for pressure sensor',
    ),
    userlimits = Param(
        default=[1e-6, 1e-3],
        datatype={"type":"limit","members":{"type":"double", "min":0,"max":1000, "unit":"mbar"}},
        description='current user set limits for the pressure regulation.',
        readonly=False,
    ),
    pollinterval = Param(visibility='expert'),
)
