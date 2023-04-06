Node('scaleint.HZB',  # a globally unique identification
     'scaledInt Test sec-Node',  # describes the node
      'tcp://10771',
      implementor = 'Peter Wegmann')  # you might choose any port number > 1024
Mod('scaleint',  # the name of the module
    'frappy_HZB.test_scaled.ScaleInt',  # the class used for communication
    'ScaleInt',  # a description
    value= 1  # the serial connection
)    
    