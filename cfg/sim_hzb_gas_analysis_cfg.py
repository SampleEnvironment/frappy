Node('gas_analysis',
    'Gas Analysis\n\n'
    'Collection of functionalities needed for the analysis of the gas after and before the catalytic process.',
    'tcp://10802',
    
)

Mod('mass_spec',
    'frappy_HZB.mass_spectrometer.MassSpectrometer',
    'A simulated mass spectrometer ',
    pollinterval = Param(export=False),
)


