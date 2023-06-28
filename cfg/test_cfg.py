Node('test.config.frappy.demo',
     '''short description of the testing sec-node

This description for the node can be as long as you need if you use a multiline string.

Very long!
The needed fields are Equipment id (1st argument), description (this)
 and the main interface of the node (3rd arg)
''',
     'tcp://10768',
)

Mod('attachtest',
    'frappy_demo.test.WithAtt',
    'test attached',
    att = 'LN2',
)

Mod('pinata',
    'frappy_demo.test.Pin',
    'scan test',
)

Mod('recursive',
    'frappy_demo.test.RecPin',
    'scan test',
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

Mod('Decision',
    'frappy_demo.test.Mapped',
    'Random value from configured property choices. Config accepts anything ' \
    'that can be converted to a list',
    choices = ['Yes', 'Maybe', 'No'],
)

Mod('c',
    'frappy_demo.test.Commands',
    'a command test',
)
