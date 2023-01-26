Coding
======

.. _class_coding:

Coding a Class for a SECoP Module
---------------------------------

A SECoP module is represented as an instance of a python class.
For programming such a class, typically you create a
subclass of one of the base classes :class:`Readable <frappy.modules.Readable>`,
:class:`Writable <frappy.modules.Writable>` or :class:`Drivable <frappy.modules.Drivable>`.
It is also quite common to inherit from classes created for similar modules,
and or to inherit from a mixin class like :class:`HasIO <frappy.io.HasIO>`.

For creating the :ref:`parameters <module structure parameters>`,
class attributes are used, using the name of
the parameter as the attribute name and an instantiation of :class:`frappy.params.Parameter`
for defining the parameter. If a parameter is already given by an inherited class,
the parameter declaration might be omitted, or just its altered properties
have to be given.

In addition, you might need one or several configurable items
(see :ref:`properties <module structure properties>`), declared in the same way, with
``<property name> =`` :class:`frappy.params.Property` ``(...)``.

For each of the parameters, the behaviour has to be programmed with the
following access methods:

def read\_\ *<parameter>*\ (self):
    Called on a ``read`` SECoP message and whenever the internal poll mechanism
    of Frappy tries to get a new value. The return value should be the
    retrieved value.
    In special cases :data:`Done <frappy.modules.Done>` might be returned instead,
    when the internal code has already updated the parameter, or
    when the value has not changed and no updates should be emitted.
    This method might also be called internally, in case a fresh value of
    the parameter is needed.

.. admonition:: polling

    The Frappy framework has a built in :ref:`polling <polling>` mechanism,
    which calls above method regularely. Each time ``read_<parameter>`` is
    called, the Frappy framework ensures then that the value of the parameter
    is updated and the activated clients will be notified by means of an
    ``update`` message.

def write\_\ *<parameter>*\ (self, value):
    Called on a ``change`` SECoP message. The ``value`` argument is the value
    given by the change message, and the method should implement the change,
    typically by handing it over to the hardware. On success, the method must
    return the accepted value. If the value may be read back
    from the hardware, the readback value should be returned, which might be
    slighly altered for example by rounding. The idea is, that the returned
    value would be the same, as if it would be done by the ``read_<parameter>``
    method. Often the easiest implementation is just returning the result of
    a call to the ``read_<parameter>`` method.
    Also, :ref:`Done <done unique>` might be returned in special
    cases, e.g. when the code was written in a way, when self.<parameter> is
    assigned already before returning from the method.

.. admonition:: behind the scenes

   Assigning a parameter to a value by setting the attribute via
   ``self.<param> = <value>`` or ``<module>.<param> = <value>`` includes
   a :ref:`type check <type check>`, some type conversion and ensures that
   a :ref:`notification <client notification>` with an
   ``update`` message is sent to all activated clients.

Example code:

.. code:: python

    from frappy.core import HasIO, Drivable, Property, Parameter, StringType

    class TemperatureLoop(HasIO, Drivable):
        """a temperature sensor with loop"""
        # internal property to configure the channel
        channel = Property('the Lakeshore channel', datatype=StringType())
        # modifying a property of inherited parameters (unit is propagated to the FloatRange datatype)
        value = Parameter(unit='K')
        target = Parameter(unit='K')

        def read_value(self):
            # using the inherited HasIO.communicate method to send a command and get the reply
            reply = self.communicate(f'KRDG?{self.channel}')
            return float(reply)

        def read_status(self):
            ... determine the status from the hardware and return it ...
            return status_code, status_text

        def read_target(self):
            ... read back the target value ...
            return target

        def write_target(self, target):
            ... write here the target to the hardware ...
            # important: make sure that the status is changed to BUSY within this method:
            self.status = BUSY, 'target changed'
            return self.read_target()  # return the read back value



.. TODO: io, state machine, persistent parameters, rwhandler, datatypes, features, commands, proxies
