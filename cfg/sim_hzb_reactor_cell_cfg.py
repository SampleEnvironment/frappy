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
target=293.15,
looptime=1,
ramp=500,
pollinterval = Param(export=False),
value = 293.15,
meaning = {
    "key":"PLACEHOLDER",
    "link":"https://w3id.org/nfdi4cat/PLACEHOLDER",
    "function":"temperature_regulation",
    "importance": 40,
    "belongs_to":"sample"}

)




Mod('temperature_sam',
    'frappy_HZB.temp_reg.TemperatureSensor',
    'A simulated Temperature Sensor ',
    group='temp_sens',
    looptime=1,
    pollinterval = Param(export=False),
    value = 293.15,
    heat_flux = 0.2,    
    attached_temp_reg = "temperature_reg",
    meaning = {   "key":"PLACEHOLDER",
        "link":"https://w3id.org/nfdi4cat/PLACEHOLDER",
        "function":"temperature",
        "importance": 40,
        "belongs_to":"sample"}


)

