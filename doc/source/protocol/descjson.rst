Structure of the descriptive json
=================================

* json = {"modules": <list_of_modules>, "properties": <list_of_sec-node_properties>, ...}
* module = {"name": <name_of_module>, "parameters": <list_of_parameters>, "commands": <list_of_commands>, "properties": <list_of_module_properties>}
* parameter = {"name": ..., "properties": <list_of_properties>}
* command = {"name": ..., "properties": <list_of_properties>}
* property = {"name":<name>, "datatype": <datatype>, "value": <value>}

note: property may also be [<name>,<datatype>,<value>]

