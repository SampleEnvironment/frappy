Configuration File
..................

.. _node configuration:

:Node:

    Specify the SEC-node properties.

    .. code::

        Node(equipment_id, description, interface, **kwds):

    The arguments are SECoP node properties and additional internal node configurations

    :Parameters:

        - **equipment_id** - a globally unique string identifying the SEC node
        - **description** - a human readable description of the SEC node
        - **interface** - an uri style string indication the address for the server
        - **kwds** - other SEC node properties

.. _mod configuration:

:Mod:

    Create a SECoP module.

    .. code::

        Mod(name, cls, description, **kwds)

    Keyworded argument matching a parameter name are used to configure
    the initial value of a parameter. For configuring the parameter properties
    the value must be an instance of **Param**, using the keyworded arguments
    for modifying the default values of the parameter properties. In this case,
    the initial value may be given as the first positional argument.
    In case command properties are to be modified **Command** has to be used.

    :Parameters:

        - **name** - the module name
        - **cls** - a qualified class name or the python class of a module
        - **description** - a human readable description of the module
        - **kwds** - parameter, property or command configurations

.. _param configuration:

:Param:

    Configure a parameter

    .. code::

        Param(value=<undef>, **kwds):

    :Parameters:

        - **value** - if given, the initial value of the parameter
        - **kwds** - parameter or datatype SECoP properties (see :class:`frappy.param.Parameter`
          and :class:`frappy.datatypes.Datatypes`)

.. _io configuration:

:IO:

    Configure IO modules (communicators)

    .. code::

        IO(<io name>, <uri>, ...)


    It is recommended that the class of the needed IO is specified as class
    attribute ioClass on the modules class. In this case, for the configuration
    of the IO modules only their name and URI is needed, for example:

    .. code::

        IO('io_T', 'tcp://192.168.1.1:7777', export=False)
        IO('io_C', 'serial:///dev/tty_USB0&baudrate=9600', export=False)

        Mod('T_sample', 'frappy_psi.lakeshore.TemperatureSensor', 'the sample T',
            io='io_T', channel='C')
        Mod('T_main', 'frappy_psi.lakeshore.TemperatureLoop', 'the main T',
            io='io_T', channel='A')
        Mod('C_sample', 'frappy_psi.ah2700.Capacitance', 'the sample capacitance',
            io='io_C')

    The ``export=False`` argument tells Frappy to hide both communicators.


.. _command configuration:

:Command:

    Configure a command

    .. code::

        Command(**kwds)

    :Parameters:

        - **kwds** - command SECoP properties (see :class:`frappy.param.Commands`)
