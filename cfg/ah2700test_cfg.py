Node('AH2700Test.psi.ch',
     'AH2700 capacitance bridge test',
     'tcp://5000',
)

Mod('cap',
    'frappy_psi.ah2700.Capacitance',
    'capacitance',
    uri='ldmse3-ts:3015',
)
