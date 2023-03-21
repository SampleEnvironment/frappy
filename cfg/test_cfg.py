Node('test.config.frappy.demo',
     '''short description of the testing sec-node

This description for the Nodecan be as long as you need if you use a multiline string.

Very long!
The needed fields are Equipment id (1st argument), description (this)
 and the main interface of the node (3rd arg)
''',
     'tcp://10768',
)

Mod('LN2',
    'frappy_demo.test.LN2',
    'random value between 0..100%',
    value = Param(default = 0, unit = '%'),
)

Mod('heater',
    'frappy_demo.test.Heater',
    'some heater',
    maxheaterpower = 10,
)

Mod('T1',
    'frappy_demo.test.Temp',
    'some temperature',
    sensor = 'X34598T7',
)

Mod('T2',
    'frappy_demo.test.Temp',
    'some temperature',
    sensor = 'X34598T8',
)

Mod('T3',
    'frappy_demo.test.Temp',
    'some temperature',
    sensor = 'X34598T9',
)

Mod('Lower',
    'frappy_demo.test.Lower',
    'something else',
)
