Node('reactor_cell',
    'Reactor Cell\n\n'
    'Collection of functionalities needed for the temperature at the sample position'
    ' and for the readout of pressures directly before and after the reactor cell.',
    'tcp://10801',
    
)



Mod('temperature_reg',
'frappy_HZB.temp_reg.TemperatureController',
'A simulated temperature controller ',
group='temp control',
target=0,
looptime=1,
ramp=60,
pollinterval = Param(export=False),
value = 0,

)




Mod('temperature_sam',
    'frappy_HZB.temp_reg.TemperatureSensor',
    'A simulated Temperature Sensor ',
    group='temp_sens',
    looptime=1,
    pollinterval = Param(export=False),
    value = 0,
    heat_flux = 0.2,
    attached_temp_reg = "temperature_reg",

)

