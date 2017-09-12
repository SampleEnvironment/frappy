Datatypes
=========

.. list-table::
    :header-rows: 1

    * - Data type
      - Specification (simple)
      - Specification (with limits)
      - Transport example
      - Datatype used in C/C++ API
      - Remarks 

    * - double
      - ["double"]
      - ["double", <min>, <max>]
      - 3.14159265
      - double
      -  

    * - int
      - ["int"]
      - ["int", <min>, <max>]
      - -55
      - int64_t
      -

    * - bool
      - ["bool"]
      -
      - true
      - int64_t
      -

    * - enum
      - ["enum", {<name> : <value>, ....}]
      -
      - 1
      - int64_t
      -

    * - string
      - ["string"]
      - ["string", <min len>, <max len>]
      - "hello!"
      - char *
      -

    * - blob
      - ["blob"]
      - ["blob", <min len>, <max len>]
      - "AA=="
      - struct {int64_t len, char \*data}
      - transport is base64 encoded

    * - array
      - ["array", <basic type>]
      - ["array", <basic type>, <min len>, <max len>]
      - [3,4,7,2,1]
      - <basic_datatype>[]
      -

    * - tuple
      - ["tuple", [<datatype>, <datatype>, ...]]
      -
      - [0,"idle"]
      - struct ??
      - 

    * - struct
      - ["struct", {<name> : <datatype>, <name>: <datatype>, ....}]
      -
      - {"x": 0, "y": 1}
      - struct ??
      -
      

