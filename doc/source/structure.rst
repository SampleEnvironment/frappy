Structure
---------

Node Structure
..............

Before starting to write the code for drivers, you have to think about
the node structure. What are the modules I want to create? What is to
be represented as a SECoP module, what as a parameter? At this point
you should not look what the hardware offers (e.g. channels A and B of
a temperature controller), but on what you need for doing an
experiment. Typically, each quantity you measure or control, has to
be represented by a module. You need module parameters for influencing
how you achieve or control the quantity. And you will need configurable
internal properties to configure the access to the hardware.


Examples:

- A temperature sensor, without an attached control loop, should inherit
  from :class:`Readable <frappy.modules.Readable>`

- A temperature sensor with a control loop should inherit from
  :class:`Drivable <frappy.modules.Drivable>`. You will need to implement a criterion for
  deciding when the temperature is reached (e.g. tolerance and time window)

- If the heater power is a quantity of interest, it should be its own
  module inheriting from :class:`Writable <frappy.modules.Writable>`.

- If it is a helium cryostat, you may want to implement a helium level
  reading module inheriting from :class:`Readable <frappy.modules.Readable>`


.. _module structure parameters:

Module Structure: Parameters
............................

The next step is to determine which parameters we need in addition to
the standard ones given by the inherited class. As a temperature sensor
inherits from :class:`Readable <frappy.modules.Readable>`, it has already a ``value``
parameter representing the measured temperature. It has also a
``status`` parameter, indicating whether the measured temperature is
valid (``IDLE``), invalid (``ERROR``) or there might be a less
critical issue (``WARN``). In addition you might want additional
parameters, like an alarm threshold.

For the controlled temperature, in addition to above, inherited from
:class:`Drivable <frappy.modules.Drivable>` it has a writable ``target`` parameter.
In addition we might need control parameters or a changeable target limits.

For the heater you might want to have a changeable power limit or power range.


.. _module structure properties:

Module Structure: Properties
............................

For the access to the hardware, we will need internal properties for
configuring the hardware access. This might the IP address of a
LAN connection or the path of an internal serial device.
In Frappy, when inheriting from the mixin :class:`HasIO <frappy.io.HasIO>`,
either the property ``io`` referring to an explicitly configured
communicator or the ``uri`` property, generating a communicator with
the given uri can be used for this.

In addition, depending on the hardware probably you need a property to
configure the channel number or name assigned to the module.

For the heater output, you might need to configure the heater resistance.


Parameter Structure
...................

A parameter also has properties, which have to be set when declaring
the parameter. Even for the inherited parameters, often the properties
have to be overriden. For example, the ``unit`` property of the ``value``
parameter on the temperature sensor will be set to 'K', and the ``max``
property of the ``target`` parameter should be set to the maximum possible
value for the hardware. This value may then probably get more restricted
by an entry in the configuration file.