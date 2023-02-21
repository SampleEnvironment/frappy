Node('softcal.demo.example',
    'convert r2 from PPMS to a temperature',
    'tcp://5001',
)

Mod('r2',
    'frappy.core.Proxy',
    'convert r2 from PPMS to a temperature',
    remote_class = 'frappy.core.Readable',
    uri = 'tcp://localhost:5000',
    export = False,
)

Mod('T2',
    'frappy_psi.softcal.Sensor',
    '',
    value = Param(unit = 'K'),
    rawsensor = 'r2',
    calib = 'X131346',
)
