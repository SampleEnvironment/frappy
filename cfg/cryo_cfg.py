#####################################################################
# Python version of frappy config
#####################################################################

Node('cryo_7.frappy.demo',
    'short description\n\n'
    'This is a very long description providing all the gory details '
    'about the stuff we are describing.',
    'tcp://10769',
    more="blub",
)

Mod('cryo',
    'frappy_demo.cryo.Cryostat',
    'A simulated cc cryostat with heat-load, specific heat for the sample and a '
    'temperature dependent heat-link between sample and regulation.',
    group='very important/stuff',
    jitter=0.1,
    T_start=10.0,
    target=10.0,
    looptime=1,
    ramp=6,
    maxpower=50.0,
    heater=4.1,
    mode='pid',
    tolerance=1,
    window=3,
    timeout=900,
    p = Param(40, unit='%/K'),  # in case 'default' is the first arg, we can omit 'default='
    i = 10,
    d = 2,
    pid = Group('p', 'i', 'd'),
    pollinterval = Param(export=False),
    value = Param(unit = 'K', test = 'customized value'),
)
