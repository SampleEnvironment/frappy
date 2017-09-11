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
* encode as ["string"] ["blob"] ["int"] ["double"] ["bool"] ["enum", {&lt;number_value&gt;:&lt;name&gt;}]
* send as json_string [length, json_string] number number 0_or_1 number_value
* complex data types: array, tuple, struct
* encode as: ["array", &lt;subtype&gt;] ["tuple", [&lt;list_of_compositing data types&gt;] ["struct", {"name_of_subcomponent":&lt;type of subcomponent&gt;}]
* send as [array] [array} {mapping}
* forbid: structs in structs, nesting level &gt; 3, arrays may only contain basic types + tuple
* essential features should not rely on complex data types
* fallback: if ECS can not handle a non-basic datatype: handle as string containing the JSON-representation.
* mandatory for all ECS: enum, int, double, string, bool, tuple(enum,string)

Merge datatype and validator
++++++++++++++++++++++++++++

* ["enum", {&lt;number_value&gt;:&lt;json_string&gt;}]
* ["int"] or ["int", &lt;lowest_allowed_value&gt;, &lt;highest_allowed_value&gt;]
* ["double"] or ["double", &lt;lowest_allowed_value&gt;, &lt;highest_allowed_value&gt;]
* ["bool"]
* ["blob", &lt;maximum_size_in_bytes&gt;] or ["blob", &lt;minimum_size_in_bytes&gt;, &lt;maximum_size_in_bytes&gt;]
* ["string", &lt;maximum_allowed_length&gt;] or ["string", &lt;min_size&gt;, &lt;max_size&gt;]
* ["array", &lt;basic_data_type&gt;, &lt;max_elements&gt;] or ["array", &lt;dtype&gt;, &lt;min_elements&gt;, &lt;max_elements&gt;]
* ["tuple", [ &lt;list_of_dtypes ]]
* ["struct", { &lt;name_of_component_as_json_string&gt;:&lt;dtype&gt;}]

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
  * ["blob", &lt;maximum_size_in_bytes&gt;] or ["blob", &lt;maximum_size_in_bytes&gt;, &lt;minimum_size_in_bytes&gt;]
  * ["string", &lt;maximum_allowed_length&gt;] or ["string", &lt;max_size_in_bytes&gt;, &lt;minimum_size_in_bytes&gt;]
  * ["array", &lt;basic_data_type&gt;, &lt;max_elements&gt;] or ["array", &lt;dtype&gt;, &lt;max_elements&gt;, &lt;min_elements&gt;]

Interface_class
+++++++++++++++

  * Drivable, Writable, Readable, Module (first character uppercase, no middle 'e')

