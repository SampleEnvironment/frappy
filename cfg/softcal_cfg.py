Node('r3',
    'temp sensor on 3He system',
    'tcp://pc12694:5000',
    cls = 'frappy.core.Proxy',
    remote_class = 'frappy_mlz.amagnet.GarfieldMagnet',
    #remote_class = 'frappy.core.Readable',
    export = False,
)

Mod('t3',
    'frappy_psi.softcal.Sensor',
    '',
    value = Param(unit = 'K'),
    rawsensor = 'r3',
    calib = 'X131346',
)
