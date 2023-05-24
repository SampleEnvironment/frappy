description = """
3He system in Lab ...
"""
Node('mlz_seop',
    description,
    'tcp://10767',
)

Mod('cell',
    'frappy_mlz.seop.Cell',
    'interface module to the driver',
    config_directory = '/home/jcns/daemon/config',
)

Mod('afp',
    'frappy_mlz.seop.Afp',
    'controls the afp flip of the cell',
    cell = 'cell'
)

Mod('nmr',
    'frappy_mlz.seop.Nmr',
    'controls the ',
    cell = 'cell'
)

fitparams = [
    ('amplitude', 'V'),
    ('T1', 's'),
    ('T2', 's'),
    ('b', ''),
    ('frequency', 'Hz'),
    ('phase', 'deg'),
]
for param, unit in fitparams:
    Mod(f'nmr_{param.lower()}',
        'frappy_mlz.seop.FitParam',
        f'fittet parameter {param} of NMR',
        cell = 'cell',
        value = Param(unit=unit),
        sigma = Param(unit=unit),
        param = param,
    )
