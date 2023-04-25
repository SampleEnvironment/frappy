Node('LscSIM.psi.ch',
    'Lsc370 Test',
     'tcp://5000',
)

Mod('io',
    'frappy_psi.ls370res.StringIO',
    'io for Ls370',
    uri = 'localhost:2089',
    )
Mod('sw',
    'frappy_psi.ls370res.Switcher',
    'channel switcher',
    io = 'io',
)
Mod('res1',
    'frappy_psi.ls370res.ResChannel',
    'resistivity chan 1',
    vexc = '2mV',
    channel = 1,
    switcher = 'sw',
)
Mod('res2',
    'frappy_psi.ls370res.ResChannel',
    'resistivity chn 3',
    vexc = '2mV',
    channel = 3,
    switcher = 'sw',
)
