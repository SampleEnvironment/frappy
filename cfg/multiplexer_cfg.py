Node('multiplexer',
    'multiplexer node',
    'tcp://5000',
    cls = 'protocol.router.Router',
    nodes = ['localhost:10768', 'localhost:10769'],
)
