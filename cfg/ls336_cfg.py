from os import environ

# either change the uri or set the environment variable 'LS_URI'
lakeshore_uri = environ.get('LS_URI', 'tcp://<host>:7777')

Node('example_cryo.psi.ch',  # a globally unique identification
     'this is an example cryostat for the Frappy tutorial',  # describes the node
      interface='tcp://10767')  # you might choose any port number > 1024
IO('io', lakeshore_uri)  # the communicator (its class will be detected automatically)
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
