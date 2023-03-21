Node('sim.test.config',
    'description of the simulation sec-node\n'
    '\n'
    'Testing simulation dummy setup.',
    'tcp://10767',
)


Mod('sim',
    'frappy.simulation.SimDrivable',
    'simulation stuff',
    extra_params = 'param3,param4,jitter,ramp',
    param3 = Param(default=True, datatype={'type': 'bool'}, readonly=False),
    jitter = 1,
    ramp = 60,
    value = 123,
    target = 42,
)
