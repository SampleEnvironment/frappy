Node('gas_dosing',
    'Gas dosing\n\n'
    'Gas dosing Node, with simulated hardware',
    'tcp://10800',
    
)

Gases = ["He","O2","CO"]
nMFC = 3

for i in range(0,nMFC):
    Mod('massflow_contr%d' % (i+1),
    'frappy_HZB.massflow_controller.MassflowController',
    'A simulated massflow controller ',
    group='massflow',
    target=0,
    looptime=1,
    ramp=6,
    pollinterval = Param(export=False),
    value = 0,
    gastype = Gases[i]
    )




Mod('backpressure_contr1',
    'frappy_HZB.pressure_controller.PressureController',
    'A simulated pressure controller ',
    group='pressure',
    target=0,
    looptime=1,
    ramp=0,
    pollinterval = Param(export=False),
    value = 0,
    attached_mfc1 = "massflow_contr1",
    attached_mfc2 = "massflow_contr2",
    attached_mfc3 = "massflow_contr3",

)

