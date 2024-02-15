Node('gas_dosing',
    'Gas dosing\n\n'
    'Gas dosing Node, with simulated hardware',
    'tcp://10800',
    
)

Mod('massflow_contr1',
    'frappy_HZB.massflow_controller.MassflowController',
    'A simulated massflow controller ',
    group='massflow',
    target=0,
    looptime=1,
    ramp=6,
    pollinterval = Param(export=False),
    value = 0,
)
