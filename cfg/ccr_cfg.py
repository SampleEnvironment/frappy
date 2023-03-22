desc = '''CCR box of MLZ Sample environment group

 Contains a Lakeshore 336 and an PLC controlling the compressor
 and some valves.'''
Node('MLZ_ccr',
     desc,
    'tcp://10767',
)

Mod('automatik',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'controls the (simple) pressure regulation\n'
    '\n'
    'selects between off, regulate on p1 or regulate on p2 sensor',
    tangodevice = 'tango://localhost:10000/box/plc/_automatik',
    mapping="{'Off':0,'p1':1,'p2':2}",
)

Mod('compressor',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'control the compressor (on/off)',
    tangodevice = 'tango://localhost:10000/box/plc/_cooler_onoff',
    mapping="{'Off':0,'On':1}",
)

Mod('gas',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'control the gas inlet into the ccr (on/off)\n'
    '\n'
    'note: this switches off automatically after 15 min.\n'
    'note: activation de-activates the vacuum inlet\n'
    'note: if the pressure regulation is active, it enslave this device',
    tangodevice = 'tango://localhost:10000/box/plc/_gas_onoff',
    mapping="{'Off':0,'On':1}",
)

Mod('vacuum',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'control the vacuum inlet into the ccr (on/off)\n'
    '\n'
    'note: activation de-activates the gas inlet\n'
    'note: if the pressure regulation is active, it enslave this device',
    tangodevice = 'tango://localhost:10000/box/plc/_vacuum_onoff',
    mapping="{'Off':0,'On':1}",
)

Mod('p1',
    'frappy_mlz.entangle.AnalogInput',
    'pressure sensor 1 (linear scale)',
    tangodevice = 'tango://localhost:10000/box/plc/_p1',
    value = Param(unit='mbar')
)

Mod('p2',
    'frappy_mlz.entangle.AnalogInput',
    'pressure sensor 2 (selectable curve)',
    tangodevice = 'tango://localhost:10000/box/plc/_p2',
    value = Param(unit='mbar'),
)

Mod('curve_p2',
    'frappy_mlz.entangle.NamedDigitalInput',
    'calibration curve for pressure sensor 2',
    tangodevice = 'tango://localhost:10000/box/plc/_curve',
    value = 0,
    mapping = "{'0-10V':0, '0-1000mbar':1, '1-9V to 0-1 mbar':2, \
        'DI200':3, 'DI2000':4, 'TTR100':7, 'PTR90':8, \
        'PTR225/237':9, 'ITR90':10, 'ITR100-D':11, \
        'ITR100-2':12, 'ITR100-3':13, 'ITR100-4':14, \
        'ITR100-5':15, 'ITR100-6':16, 'ITR100-7':17, \
        'ITR100-8':18, 'ITR100-9':19, 'ITR100-A':20, \
        'CMR361':21, 'CMR362':22, 'CMR363':23, \
        'CMR364':24, 'CMR365':25}",
)

Mod('T_tube_regulation',
    'frappy_mlz.entangle.TemperatureController',
    'regulation of tube temperature',
    tangodevice = 'tango://localhost:10000/box/tube/control1',
    value = Param(unit = 'K'),
    heateroutput = 0,
    ramp = 6,
    speed = 0.1,
    setpoint = 0,
    pid = (40, 10, 1),
    p = 40,
    i = 10,
    d = 1,
    abslimits = (0, 500),
)

Mod('T_stick_regulation',
    'frappy_mlz.entangle.TemperatureController',
    'regualtion of stick temperature',
    tangodevice = 'tango://localhost:10000/box/stick/control2',
    value = Param(unit = 'K'),
    heateroutput = 0,
    ramp = 6,
    speed = 0.1,
    setpoint = 0,
    pid = (40, 10, 1),
    p = 40,
    i = 10,
    d = 1,
    abslimits = (0, 500),
)
Mod('T_sample',
    'frappy_mlz.entangle.Sensor',
    'sample temperature',
    tangodevice = 'tango://localhost:10000/box/sample/sensora',
    value = Param(unit = 'K'),
)

Mod('T_stick',
    'frappy_mlz.entangle.Sensor',
    'temperature at bottom of sample stick',
    tangodevice = 'tango://localhost:10000/box/stick/sensorb',
    value = Param(unit = 'K'),
)

Mod('T_coldhead',
    'frappy_mlz.entangle.Sensor',
    'temperature at coldhead',
    tangodevice = 'tango://localhost:10000/box/coldhead/sensorc',
    value = Param(unit = 'K'),
)

Mod('T_tube',
    'frappy_mlz.entangle.Sensor',
    'temperature at thermal coupling tube <-> stick',
    tangodevice = 'tango://localhost:10000/box/tube/sensord',
    value = Param(unit = 'K'),
)

# THIS IS A HACK: due to entangle (in controller)
Mod('T_tube_regulation_heaterrange',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'heaterrange for tube regulation',
    tangodevice = 'tango://localhost:10000/box/tube/range1',
    mapping="{'Off':0,'Low':1,'Medium':2, 'High':3}",
)

Mod('T_stick_regulation_heaterrange',
    'frappy_mlz.entangle.NamedDigitalOutput',
    'heaterrange for stick regulation',
    tangodevice = 'tango://localhost:10000/box/stick/range2',
    mapping="{'Off':0,'Low':1,'Medium':2, 'High':3}",
)
