Node('demo.frappy.demo',
     'Basic demo server for frappy',
     'tcp://10767',
)

Mod('heatswitch',
    'frappy_demo.modules.Switch',
    'Heatswitch for `mf` device',
    switch_on_time = 5,
    switch_off_time = 10,
)

Mod('mf',
    'frappy_demo.modules.MagneticField',
    'simulates some cryomagnet with persistent/non-persistent switching',
    heatswitch = 'heatswitch',
)

Mod('ts',
    'frappy_demo.modules.SampleTemp',
    'some temperature',
    sensor = 'Q1329V7R3',
    ramp = 4,
    target = 10,
    value = 10,
)

Mod('tc1',
    'frappy_demo.modules.CoilTemp',
    'some temperature',
    sensor = 'X34598T7',
)

Mod('tc2',
    'frappy_demo.modules.CoilTemp',
    'some temperature',
    sensor = 'X39284Q8',
)

Mod('label',
    'frappy_demo.modules.Label',
    'some label indicating the state of the magnet `mf`.',
    system = 'Cryomagnet MX15',
    subdev_mf = 'mf',
    subdev_ts = 'ts',
)
