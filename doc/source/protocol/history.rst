History
=======

Meeting 29.5.2017
-----------------

* for api: float is 'double'
* everything countable is int64_t
* description is string (UTF-8 without embedded \0) (zero terminated for API)
* names / identifiers are:  [_a-z][_a-z0-9]{0,63}
* BLOB is [length, string_encoding (base64 or json_string) ] ???
* enum is transferred by value (api: int64_t)
* basic data types: string, BLOB(maxsize), int, double, bool, enum(mapping)
* encode as ["string"] ["blob"] ["int"] ["double"] ["bool"] ["enum", {<number_value>:<name>}]
* send as json_string [length, json_string] number number 0_or_1 number_value
* complex data types: array, tuple, struct
* encode as: ["array", <subtype>] ["tuple", [<list_of_compositing data types>] ["struct", {"name_of_subcomponent":<type of subcomponent>}]
* send as [array] [array} {mapping}
* forbid: structs in structs, nesting level > 3, arrays may only contain basic types + tuple
* essential features should not rely on complex data types
* fallback: if ECS can not handle a non-basic datatype: handle as string containing the JSON-representation.
* mandatory for all ECS: enum, int, double, string, bool, tuple(enum,string)

Merge datatype and validator
++++++++++++++++++++++++++++

* ["enum", {<number_value>:<json_string>}]
* ["int"] or ["int", <lowest_allowed_value>, <highest_allowed_value>]
* ["double"] or ["double", <lowest_allowed_value>, <highest_allowed_value>]
* ["bool"]
* ["blob", <maximum_size_in_bytes>] or ["blob", <minimum_size_in_bytes>, <maximum_size_in_bytes>]
* ["string", <maximum_allowed_length>] or ["string", <min_size>, <max_size>]
* ["array", <basic_data_type>, <max_elements>] or ["array", <dtype>, <min_elements>, <max_elements>]
* ["tuple", [ <list_of_dtypes ]]
* ["struct", { <name_of_component_as_json_string>:<dtype>}]

Examples
++++++++

* status: ["tuple", [ ["enum", {0:"init", 100:"idle", 200:"warn", 300:"busy"}], ["string", 255] ] ]
* p/pi/pid-triple: ["array", ["double", 0, 100], 1, 3]


Meeting 30.5.2017
-----------------

* data values can be transferred as json_null, meaning: no value yet
* json_null can not be used inside structured data types
* property name for datatype is "datatype"

Meeting 11.9.2017
-----------------

Merge datatype and validator
++++++++++++++++++++++++++++

  * enum, int, double, bool, tuple, struct as before
  * ["blob", <maximum_size_in_bytes>] or ["blob", <maximum_size_in_bytes>, <minimum_size_in_bytes>]
  * ["string", <maximum_allowed_length>] or ["string", <max_size_in_bytes>, <minimum_size_in_bytes>]
  * ["array", <basic_data_type>, <max_elements>] or ["array", <dtype>, <max_elements>, <min_elements>]


Interface_class
+++++++++++++++

  * Drivable, Writable, Readable, Module (first character uppercase, no middle 'e')


transfer_of_blob
++++++++++++++++

  * transport-encoding as base64-encoded string (no prefixed number of bytes....)

