Server
------

Configuration
.............

The configuration code consists of a :ref:`Node() <node configuration>` section, and one
:ref:`Mod() <mod configuration>` section per SECoP module.

The **Node** section contains a globally unique ID of the SEC node,
a description of the SEC node and the server interface uri. Example:

.. code:: python

    Node('globally.valid.identifier',
         'a description of the SEC node',
         interface = 'tcp://5000')

For the interface scheme currently only tcp is supported.
When the TCP port is given as an argument of the server start script, **interface** is not
needed or ignored. The main information is the port number, in this example 5000.

All other :ref:`Mod() <mod configuration>` sections define the SECoP modules.
Mandatory fields are **name**, **cls** and **description**. **cls** is a path to the Python class
from where the module is instantiated, separated with dots. In the following example the class
**HeLevel** used by the **helevel** module can be found in the PSI facility subdirectory
frappy_psi in the python module file ccu4.py:

.. code:: python

    Mod('helevel',
        'frappy_psi.ccu4.HeLevel',
        'this is the He level sensor of the main reservoir',
        empty_length = Param(380, export=False),
        full = Param(0, export=False))

It is highly recommended to use all lower case for the module name, as SECoP names have to be
unique despite of casing. In addition, parameters, properties and parameter properties might
be initialized in this section. In the above example **empty_length** and **full_length** are parameters,
the resistivity of the He Level sensor at the end of the ranges. In addition, we alter the
default property **export** of theses parameters, as we do not want to expose these parameters to
the SECoP interface.


Starting
........

The Frappy server can be started via the **bin/frappy-server** script.

.. parsed-literal::

    usage: bin/frappy-server [-h] [-v | -q] [-d] [-t] [-p port] [-c cfgfiles] name

    Manage a Frappy server

    positional arguments:
      name             name of the instance. Uses <config path>/name_cfg.py for configuration

    optional arguments:
      -c, --cfgfiles   config files to be used. Comma separated list.
                       defaults to <name> when omitted
      -p, --port       server port (default: take from cfg file)
      -h, --help       show this help message and exit
      -v, --verbose    output lots of diagnostic information
      -q, --quiet      suppress non-error messages
      -d, --daemonize  run as daemon
      -t, --test       check cfg files only
