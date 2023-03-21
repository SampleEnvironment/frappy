Configuration File
..................

.. _node configuration:

:Node(equipment_id, description, interface, \*\*kwds):

    Specify the SEC-node properties.

    The arguments are SECoP node properties and additional internal node configurations

    :Parameters:

        - **equipment_id** - a globally unique string identifying the SEC node
        - **description** - a human readable description of the SEC node
        - **interface** - an uri style string indication the address for the server
        - **kwds** - other SEC node properties

.. _mod configuration:

:Mod(name, cls, description, \*\*kwds):

    Create a SECoP module.
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

:Param(value=<undef>, \*\*kwds):

    Configure a parameter

    :Parameters:

        - **value** - if given, the initial value of the parameter
        - **kwds** - parameter or datatype SECoP properties (see :class:`frappy.param.Parameter`
          and :class:`frappy.datatypes.Datatypes`)

.. _command configuration:

:Command(\*\*kwds):

    Configure a command

    :Parameters:

        - **kwds** - command SECoP properties (see :class:`frappy.param.Commands`)
