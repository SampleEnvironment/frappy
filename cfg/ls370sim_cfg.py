Node('LscSIM.psi.ch',
    'Lsc Simulation at PSI',
     'tcp://5000',
)

Mod('lscom',
    'frappy_psi.ls370sim.Ls370Sim',
    'simulated serial communicator to a LS 370',
    visibility = 3
)

Mod('sw',
    'frappy_psi.ls370res.Switcher',
    'channel switcher for Lsc controller',
    io = 'lscom',
)

Mod('a',
    'frappy_psi.ls370res.ResChannel',
    'resistivity',
    channel = 1,
    switcher = 'sw',
)

Mod('b',
    'frappy_psi.ls370res.ResChannel',
    'resistivity',
    channel = 3,
    switcher = 'sw',
)
