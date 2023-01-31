Node('example_cryo.psi.ch',  # a globally unique identification
     'this is an example cryostat for the Frappy tutorial',  # describes the node
      interface='tcp://10767')  # you might choose any port number > 1024
Mod('io',  # the name of the module
    'frappy_demo.lakeshore.LakeshoreIO',  # the class used for communication
    'communication to main controller',  # a description
    uri='tcp://129.129.138.78:7777',  # the serial connection
    )
Mod('T',
    'frappy_demo.lakeshore.TemperatureLoop',
    'Sample Temperature',
    io='io',
    channel='A',  # the channel on the LakeShore for this module
    loop=1,  # the loop to be used
    value=Param(max=470),  # set the maximum expected T
    target=Param(max=420),  # set the maximum allowed target T
    heater_range=3,  # 5 for model 350
    )
