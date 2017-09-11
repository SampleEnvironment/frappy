Starting
========

The SECoP server can be started via the ``bin/secop-server`` script.

.. parsed-literal::

    usage: secop-server [-h] [-v | -q] [-d] name

    Manage a SECoP server

    positional arguments:
      name             Name of the instance. Uses etc/name.cfg for configuration

    optional arguments:
      -h, --help       show this help message and exit
      -v, --verbose    Output lots of diagnostic information
      -q, --quiet      suppress non-error messages
      -d, --daemonize  Run as daemon


