### Getting started:

## 1. Config file für den Roboter anpassen: 
```cfg/UR_robot_cfg```



SEC-Node Port und Roboter IP-Adresse eintragen:

Also ``SECNODEPORT`` und ``ROBOT-IP-ADRESS`` in ```cfg/UR_robot_cfg``` ersetzen.
```python
Node('sample_changer.HZB',  # a globally unique identification
     'Sample Changer\n\nThis is an demo for a  SECoP (Sample Environment Communication Protocol) sample changer SEC-Node.',  # describes the node
      'tcp://SECNODEPORT',
      implementor = 'Peter Wegmann')

Mod('io',  # the name of the module
    'frappy_HZB.robo.RobotIO',  # the class used for communication
    'TCP communication to robot Dashboard Server Interface',  # a description
    uri='tcp://ROBOT-IP-ADRESS:29999',  # the serial connection
```
## 2. Bevor die SEC-Node gestartet werden kann müssen einige Ports weitergeleitet werden (roboter IP am Schluss einfügen):

Folgender Befehl leitet die Ports weiter:
```ssh -L 29999:localhost:29999 -L 30001:localhost:30001 -L 30002:localhost:30002 -L 30003:localhost:30003 -L 30004:localhost:30004 ur@<roboIP>```

Das Passwort des Roboters ist ``easybot``

## 3. SEC-Node Starten
```/bin/frappy-server -c UR_robot_cfg.py robo```


## Trouble shooting:

 -``STATUS: LOCAL_CONTROL``: Roboter ist im ``local control`` modus. Der Roboter kann nur am controller Tablet in den ``remote control`` modus umgestellt werden. 

 -``STATUS: DISABLED (POWER_OFF)``: ``POWER_ON`` in das accessible ``powerstate`` im ``robot`` Modul schreiben.

POWER_ON: ``change robot:_powerstate 2`` 

POWER_OFF: ``change robot:_powerstate 1`` 


