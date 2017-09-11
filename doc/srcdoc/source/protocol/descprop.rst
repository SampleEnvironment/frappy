Descriptive properties
======================

Mandatory descriptive properties
--------------------------------

parameter-properties
++++++++++++++++++++

* name (implicit)
* datatype
* readonly (bool)

module-properties
+++++++++++++++++

* interface_class [list_of_strings] (MAY be empty)

SEC-Node-properties
+++++++++++++++++++

* no mandatory properties

Optional descriptive properties
-------------------------------

parameter-properties
++++++++++++++++++++

* unit (string), SHOULD be given if meaningful (if not given: unitless) (empty string: unit is one)
* description (string), SHOULD be given
* visibility
* group (identifier) (MUST start with an uppercase letter) (if empty string: treat as not specified)

module-properties
+++++++++++++++++

* description (string), SHOULD be given
* visibility
* group (identifier) (MUST start with an uppercase letter) (if empty string: treat as not specified)
* meaning ???
* importance ???

SEC-Node-properties
+++++++++++++++++++

* description (string), SHOULD be given

