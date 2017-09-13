Datatypes
=========

double
------

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["double"] **or**
        | ["double", <min>] **or**
        | ["double", <min>, <max>]
        |
        | if <max> is not given or null, there is no upper limit
        | if <min> is null or not given, there is no lower limit

    * - Transport example
      - | 3.14159265

    * - Datatype in C/C++
      - | double

int
---

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["int"] **or**
        | ["int", <min>] **or**
        | ["int", <min>, <max>]
        |
        | if <max> is not given or null, there is no upper limit
        | if <min> is null or not given, there is no lower limit

    * - Transport example
      - | -55

    * - Datatype in C/C++
      - | int64_t

bool
----

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["bool"]

    * - Transport example
      - | true

    * - Datatype in C/C++
      - | int64_t


enum
----

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["enum", {<name> : <value>, ....}]

    * - Transport example
      - | 2

    * - Datatype in C/C++
      - | int64_t


string
------

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["string"] **or**
        | ["string", <max len>] **or**
        | ["string", <max len>, <min len>]
        |
        | if <max len> is not given, it is assumed as 255.
        | if <min len> is not given, it is assumed as 0.
        | if the string is UTF-8 encoded, the length is counting the number of bytes, not characters

    * - Transport example
      - | "hello!"

    * - Datatype in C/C++
      - | char \*

blob
----

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["blob", <max len>] **or**
        | ["blob", <max len>, <min len>]
        |
        | if <min len> is not given, it is assumed as 0.

    * - Transport example
      - | "AA=="  (base64 encoded)

    * - Datatype in C/C++
      - | struct {int64_t len, char \*data}

array
-----

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["array", <basic type>, <max len>] **or**
        | ["array", <basic type>, <max len>, <min len>]
        |
        | if <min len> is not given, it is assumed as 0.
        | the length is the number of elements

    * - Transport example
      - | [3,4,7,2,1]

    * - Datatype in C/C++
      - | <basic_datatype>[]
 
tuple
-----

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["tuple", [<datatype>, <datatype>, ...]]

    * - Transport example
      - | [0,"idle"]

    * - Datatype in C/C++
      - | struct ??

struct
------

.. list-table::
    :widths: 20 80
    :stub-columns: 1

    * - Datatype
      - | ["struct", {<name> : <datatype>, <name>: <datatype>, ....}]

    * - Transport example
      - | {"x": 0, "y": 1}

    * - Datatype in C/C++
      - | struct ??
        |
        | might be null
