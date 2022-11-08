Configuration
.............

The configuration consists of a **NODE** section, an **INTERFACE** section and one
section per SECoP module.

The **NODE** section contains a description of the SEC node and a globally unique ID of
the SEC node. Example:

.. code::

    [NODE]
    description = a description of the SEC node
    id = globally.valid.identifier

The **INTERFACE** section defines the server interface. Currently only tcp is supported.
When the TCP port is given as an argument of the server start script, this section is not
needed or ignored. The main information is the port number, in this example 5000:

.. code::

    [INTERFACE]
    uri = tcp://5000


All other sections define the SECoP modules. The section name itself is the module name,
mandatory fields are **class** and **description**. **class** is a path to the Python class
from there the module is instantiated, separated with dots. In the following example the class
**HeLevel** used by the **helevel** module can be found in the PSI facility subdirectory
frappy_psi in the python module file ccu4.py:

.. code::

    [helevel]
    class = frappy_psi.ccu4.HeLevel
    description = this is the He level sensor of the main reservoir
    empty = 380
    empty.export = False
    full = 0
    full.export = False

It is highly recommended to use all lower case for the module name, as SECoP names have to be
unique despite of casing. In addition, parameters, properties and parameter properties might
be initialized in this section. In the above example **empty** and **full** are parameters,
the resistivity of the He Level sensor at the end of the ranges. In addition, we alter the
default property **export** of theses parameters, as we do not want to expose these parameters to
the SECoP interface.


Starting
........

The Frappy server can be started via the **bin/frappy-server** script.

.. parsed-literal::

    usage: frappy-server [-h] [-v | -q] [-d] name

    Manage a Frappy server

    positional arguments:
      name             name of the instance. Uses etc/name.cfg for configuration

    optional arguments:
      -c, --cfgfiles   config files to be used. Comma separated list.
                       defaults to <name> when omitted
      -p, --port       server port (default: take from cfg file)
      -h, --help       show this help message and exit
      -v, --verbose    output lots of diagnostic information
      -q, --quiet      suppress non-error messages
      -d, --daemonize  run as daemon
      -t, --test       check cfg files only
