JSON structure
==============

> Mit JSON Freeze meine ich nur Arrays von Objekten also:
> -Node hat ein Array von Properties und ein Array von Modulen
> -Module haben ein Array von Properties, ein Array von Parametern und ein Array von Commands
> -Parameter und Commands haben jeweils ein Array von Properties

node = { 'properties' : [<property>],
         'modules'    : [<module>] }

module = { 'properties' : [<property>],
           'parameter'  : [<parameter>],
           'commands'   : [<command>] }

parameter = { 'properties' : [<property>] }

commands = { 'properties' : [<property>] }

property = { 'property-name' : 'property-value' }


ODER
----

node = [ <array_of_properties>, <array_of_modules> ]

array_of_modules = [ <module>, ... ]

module = <array_of_properties>, <array_of_params>, <array_of_commands>
#OR#
module = [<array_of_properties>, <array_of_params>, <array_of_commands>]

array_of_params = [ <param>, ...]

param = <array_of_properties>

array_of_commands = [ <command>, ...]

command = < array_of_properties>

array_of_properties = [ <property>, ...]

property = 'name', 'value'
#OR#
property = ['name', 'value']
#OR#
property = {'name' : 'value'}

Oder ganz anders?

Siehe auch diskussion im HZB-wiki hierzu....

verwirrend....

vorerst folgende Festlegung:

.. code-block:: json

    {"equipment_id": "cryo_7",
     "firmware": "The SECoP playground",
     "modules": ["cryo", {"commands": ["stop", {"resulttype": "None",
                                                "arguments": "[]",
                                                "description": "Testing command implementation\\n\\nwait a second"
                                               },
                                       "start", {"resulttype": "None",
                                                 "arguments": "[]",
                                                 "description": "normally does nothing,\\n\\nbut there may be modules which _start_ the action here\\n"
                                                }
                                      ],
                           "group": "very important/stuff",
                           "implementation": "secop.devices.cryo.Cryostat",
                           "interfaces": ["Drivable", "Readable", "Device"],
                           "parameters": ["status", {"readonly": true,
                                                     "datatype": ["tuple", ["enum", {"unknown":-1,"idle":100, "warn":200, "unstable":250, "busy":300,"error":400}], "string"],
                                                     "description": "current status of the device"
                                                    },
                                          "value", {"readonly": true,
                                                    "datatype": ["double",0,null],
                                                    "description": "regulation temperature",
                                                    "unit": "K"
                                                   },
                                          "target", {"readonly": false,
                                                     "datatype": ["double",0,null],
                                                     "description": "target temperature",
                                                     "unit": "K"
                                                    }
                                       ]
                           }
                  ],
     "version": "2017.01"
    }


