Node('LscSIM.psi.ch',
    'Lsc370 Test',
     'tcp://5000',
)

Mod('lsmain',
    'frappy_psi.ls370res.Main',
    'main control of Lsc controller',
    uri = 'localhost:4567',
)

Mod('res',
    'frappy_psi.ls370res.ResChannel',
    'resistivity',
    vexc = '2mV',
    channel = 3,
    main = 'lsmain',
    # the auto created iodev from lsmain:
    iodev = 'lsmain_iodev',
)
