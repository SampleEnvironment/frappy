Node('PPMS.psi.ch',
    'PPMS at PSI',
    'tcp://5000',
)

Mod('tt',
    'frappy_psi.ppms.Temp',
    'main temperature',
    io = 'ppms',
)

Mod('mf',
    'frappy_psi.ppms.Field',
    'magnetic field',
    target = Param(min=-9, max=9),
    io = 'ppms',
)

Mod('pos',
    'frappy_psi.ppms.Position',
    'sample rotator',
    io = 'ppms',
)

Mod('lev',
    'frappy_psi.ppms.Level',
    'helium level',
    io = 'ppms',
)

Mod('chamber',
    'frappy_psi.ppms.Chamber',
    'chamber state',
    io = 'ppms',
)

for i in range(1,5):
    Mod('r%d' % i,
        'frappy_psi.ppms.BridgeChannel',
        'resistivity channel %d' % i,
        no = i,
        value = Param(unit = 'Ohm'),
        io = 'ppms',
    )

for i in range(1,5):
    Mod('i%d' % i,
        'frappy_psi.ppms.Channel',
        'current channel %d' % i,
        no = i,
        value = Param(unit = 'uA'),
        io = 'ppms',
    )

Mod('v1',
    'frappy_psi.ppms.DriverChannel',
    'voltage channel 1',
    no = 1,
    value = Param(unit = 'V'),
    io = 'ppms',
)

Mod('v2',
    'frappy_psi.ppms.DriverChannel',
    'voltage channel 2',
    no = 2,
    value = Param(unit = 'V'),
    io = 'ppms',
)

Mod('tv',
    'frappy_psi.ppms.UserChannel',
    'VTI temperature',
    enabled = 1,
    value = Param(unit = 'K'),
    io = 'ppms',
)

Mod('ts',
    'frappy_psi.ppms.UserChannel',
    'sample temperature',
    enabled = 1,
    value = Param(unit = 'K'),
    io = 'ppms',
)

Mod('ppms',
    'frappy_psi.ppms.Main',
    'the main and poller module',
    class_id = 'QD.MULTIVU.PPMS.1',
    visibility = 3,
    pollinterval = 2,
)
