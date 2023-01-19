Node('filtered.PPMS.psi.ch',
    'filtered PPMS at PSI',
    'localhost:5002',
)


Mod('secnode',
    'frappy.proxy.SecNode',
    'a SEC node',
    uri = 'tcp://localhost:5000',
)

Mod('mf',
    'frappy.proxy.Proxy',
    'magnetic field',
    remote_class = 'frappy_psi.ppms.Field',
    io = 'secnode',

    value = Param(min = -0.1, max = 0.1),
    target = Param(min = -8, max = 8),
)
