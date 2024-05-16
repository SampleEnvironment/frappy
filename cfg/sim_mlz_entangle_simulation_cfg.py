Node('simulation',
    'Auto-generated configuration by frappy.',
    'tcp://10767',
)
Mod('analoginput',
    'frappy_mlz.entangle.AnalogInput',
    'from test/sim/analoginput',
    tangodevice = 'tango://localhost:10000/test/sim/analoginput',
)
Mod('sensor',
    'frappy_mlz.entangle.Sensor',
    'from test/sim/sensor',
    tangodevice = 'tango://localhost:10000/test/sim/sensor',
)
Mod('analogoutput',
    'frappy_mlz.entangle.AnalogOutput',
    'from test/sim/analogoutput',
    tangodevice = 'tango://localhost:10000/test/sim/analogoutput',
)
Mod('actuator',
    'frappy_mlz.entangle.Actuator',
    'from test/sim/actuator',
    tangodevice = 'tango://localhost:10000/test/sim/actuator',
)
Mod('motor',
    'frappy_mlz.entangle.Motor',
    'from test/sim/motor',
    tangodevice = 'tango://localhost:10000/test/sim/motor',
)
Mod('powersupply',
    'frappy_mlz.entangle.PowerSupply',
    'from test/sim/powersupply',
    tangodevice = 'tango://localhost:10000/test/sim/powersupply',
)
Mod('digitalinput',
    'frappy_mlz.entangle.DigitalInput',
    'from test/sim/digitalinput',
    tangodevice = 'tango://localhost:10000/test/sim/digitalinput',
)
Mod('digitaloutput',
    'frappy_mlz.entangle.DigitalOutput',
    'from test/sim/digitaloutput',
    tangodevice = 'tango://localhost:10000/test/sim/digitaloutput',
)
Mod('stringio',
    'frappy_mlz.entangle.StringIO',
    'from test/sim/stringio',
    tangodevice = 'tango://localhost:10000/test/sim/stringio',
)
