A Simple Temperature Controller
===============================

The Use Case
------------

Let us assume we have simple cryostat or furnace with one temperature sensor
and a heater. We want first to implement reading the temperature and then
add the control loop. Assume also we have a LakeShore temperature controller
to access the hardware.


Coding the Sensor Module
------------------------

A temperature sensor without control loop is to be implemented as a subclass
of :class:`Readable <frappy.modules.Readable>`. You create this example to be used in your
facility, so you add it to the subdirectory of your facility. You might need
to create it, if it is not already there. In this example, you may
replace *frappy_psi* by *frappy_<your facility>*. The name the python file
is chosen from the type of temperature controller *lakeshore.py*.

We assume that the temperature controller is already configured with input ``A``
being used, and the proper calibration curve assigned. In productive code
this configuration may also be done by Frappy, but this would extend the scope
of this tutorial too much.

So we define a class and define the parameter properties for the value:

``frappy_psi/lakeshore.py``:

.. code:: python

    # the most common Frappy classes can be imported from frappy.core
    from frappy.core import Readable, Parameter, FloatRange

    class TemperatureSensor(Readable):
        """a temperature sensor (generic for different models)"""
        # 1500 is the maximum T allowed for most of the lakeshore models
        # this should be further restricted in the configuration (see below)
        value = Parameter(datatype=FloatRange(0, 1500, unit='K'))


For the next step, we have to code how to retrieve the temperature
from the controller. For this we add the method ``read_value``.
In addition, we have to define a communicator class, and make
``TemperatureSensor`` inherit from :class:`HasIO <frappy.io.HasIO>`
in order to add the :meth:`communicate` method to the class.

See :ref:`lsc_manual_extract` for details of the needed commands.


.. code:: python

    from frappy.core import Readable, Parameter, FloatRange, HasIO, StringIO, Property, StringType

    class LakeshoreIO(StringIO):
        wait_before = 0.05  # Lakeshore requires a wait time of 50 ms between commands
        # '*IDN?' is sent on connect, and the reply is checked to match the regexp 'LSCI,.*'
        identification = [('*IDN?', 'LSCI,.*')]

    class TemperatureSensor(HasIO, Readable):
        """a temperature sensor (generic for different models)"""
        # internal property to configure the channel
        # see below for the difference of 'Property' and 'Parameter'
        channel = Property('the Lakeshore channel', datatype=StringType())
        # 0, 1500 is the allowed range by the LakeShore controller
        # this should be further restricted in the configuration (see below)
        value = Parameter(datatype=FloatRange(0, 1500, unit='K'))

        def read_value(self):
            # the communicate method sends a command and returns the reply
            reply = self.communicate(f'KRDG?{self.channel}')
            # convert to float
            return float(reply)


This is the code to run a minimalistic SEC Node, which does just read a temperature
and nothing else.

.. Note::

    A :class:`Property <frappy.properties.Property>` is used instead of a
    :class:`Parameter <frappy.param.Parameter>`, for a configurable item not changing
    on run time. A ``Property`` is typically only internal needed and by default not
    visible by SECoP.


Before we start the frappy server for the first time, we have to create a configuration file.
The directory tree of the Frappy framework contains the code for all drivers but the
configuration file determines, which code will be loaded when a server is started.
We choose the name *example_cryo* and create therefore a configuration file
*example_cryo_cfg.py* in the *cfg* subdirectory:

``cfg/example_cryo_cfg.py``:

.. code:: python

    Node('example_cryo.psi.ch',  # a globally unique identification
         'this is an example cryostat for the Frappy tutorial',  # describes the node
          interface='tcp://10767')  # you might choose any port number > 1024
    Mod('io',  # the name of the module
        'frappy_psi.lakeshore.LakeshoreIO',  # the class used for communication
        'communication to main controller',  # a description
        # the serial connection, including serial settings (see frappy.io.IOBase):
        uri='serial://COM6:?baudrate=57600+parity=odd+bytesize=7',
       )
    Mod('T',
        'frappy_psi.lakeshore.TemperatureSensor',
        'Sample Temperature',
        io='io',  # refers to above defined module 'io'
        channel='A',  # the channel on the LakeShore for this module
        value=Param(max=470),  # alter the maximum expected T
       )

The first section in the configuration file configures the common settings for the server.
:ref:`Node <node configuration>` describes the main properties of the SEC Node: an identifier,
which should be globally unique, a description of the node, and an interface defining the server address.
Usually the only important value in the server address is the TCP port under which the
server will be accessible. Currently only the tcp scheme is supported.

Then for each module a :ref:`Mod <mod configuration>` section follows.
We have to create the ``io`` module for communication first, with
the ``uri`` as its most important argument.
In case of a serial connection the prefix is ``serial://``. On a Windows machine, the full
uri is something like ``serial://COM6:?baudrate=9600`` on a linux system it might be
``serial:///dev/ttyUSB0?baudrate=9600``. In case of a LAN connection, the uri should
be something like ``tcp://129.129.138.78:7777`` or ``tcp://mydevice.psi.ch:7777``, where
7777 is the tcp port the LakeShore is listening to.

Now, we are ready to start our first server. In the main frappy directory, we
start it with:

.. code::

    python bin/frappy-server example_cryo

If error messages appear, you have first to try to fix the errors.
Else you might open an other console or terminal, in order to start
a frappy client, for example the GUI client. The argument is
compose by the machine running the server and the server port chosen
in the configuration file:

.. code::

    python bin/frappy-gui localhost:10767


A ``Readable`` SECoP module also has a status parameter. Until now, we completely
ignored it. As you may see, the value of status parameter is always ``(IDLE, '')``.
However, we should implement the status parameter to give information about the
validity of the sensor reading. The controller has a query command ``RDGST?<channel>``
returning a code describing error states. We implement this by adding a the
``read_status`` method to the class:

.. code:: python

    from frappy.core import Readable, Parameter, FloatRange, HasIO, StringIO, Property, StringType,\
        IDLE, ERROR

    ...

    class TemperatureSensor(HasIO, Readable):

        ...

        def read_status(self):
            code = int(self.communicate(f'RDGST?{self.channel}'))
            if code >= 128:
                text = 'units overrange'
            elif code >= 64:
                text = 'units zero'
            elif code >= 32:
                text = 'temperature overrange'
            elif code >= 16:
                text = 'temperature underrange'
            elif code % 2:
                # ignore 'old reading', as this may happen in normal operation
                text = 'invalid reading'
            else:
                return IDLE, ''
            return ERROR, text

After a restart of the server and the client, the status should change to
``ERROR, '<some error message>'`` when the sensor is unplugged.


Extend the Class to a Temperature Loop
--------------------------------------

As we want to implement also temperature control, we have extend the class more.
Instead of adding just more methods to the ``TemperatureSensor`` class, we
create a new class ``TemperatureLoop`` inheriting from Temperature sensor.
This way, we would for example be able to create a node with a controlled
temperature on one channel, and a sensor module without control on an other channel.

Temperature control is represented by a subclass of :class:`Drivable <frappy.modules.Drivable>`.
So our new class will be based on ``TemperatureSensor`` where we have already
implemented the readable stuff. We need to define some properties of the ``target``
parameter and add a property ``loop`` indicating, which control loop and
heater output we use.

In addition, we have to implement the method ``write_target``. Remark: we do not
implement ``read_target`` here, because the lakeshore does not offer to read back the
real target. The SETP command is returning the working setpoint, which may be distinct
from target during a ramp.

.. code:: python

    from frappy.core import Readable, Parameter, FloatRange, HasIO, StringIO, Property, StringType,\
        IDLE, BUSY, WARN, ERROR, Drivable, IntRange

    ...

    class TemperatureLoop(TemperatureSensor, Drivable):
        # lakeshore loop number to be used for this module
        loop = Property('lakeshore loop', IntRange(1, 2), default=1)
        target = Parameter(datatype=FloatRange(unit='K', min=0, max=1500))

        def write_target(self, target):
            # we always use a request / reply scheme
            self.communicate(f'SETP {self.loop},{target};*OPC?')
            return target


In order to test this, we will need to change the entry module ``T`` in the
configuration file:

.. code:: python

    Mod('T',
        'frappy_psi.lakeshore.TemperatureLoop',
        'Sample Temperature',
        io='io',
        channel='A',  # the channel on the LakeShore for this module
        loop=1,  # the loop to be used
        value=Param(max=470),  # set the maximum expected T
        target=Param(max=420),  # set the maximum allowed target T
       )

To test that this step worked, just restart the server and the client.
If the temperature controller is not yet configured for controlling the
temperature on channel A with loop 1, this has to be done first.
Especially the heater has to be switched on, setting the maximum heater
range.

There are two things still missing:

- We want to switch on the heater automatically, when the target is changed.
  A property ``heater_range`` is added for this.
- We want to handle the status code correctly: set to ``BUSY`` when the
  target is changed, and back to ``IDLE`` when the target temperature is reached.
  The parameter ``tolerance`` is used for this. For the tutorial we use here
  a rather simple mechanism. In reality, often over- or undershoot happens.
  A better algorithm would not switch to IDLE before the temperature was within
  tolerance for some given time.


.. code:: python

    from frappy.core import Readable, Drivable, Parameter, FloatRange, \
        HasIO, StringIO, IDLE, BUSY, WARN, ERROR

    ...

    class TemperatureLoop(TemperatureSensor, Drivable):
        ...
        heater_range = Property('heater power range', IntRange(0, 5))  # max. 3 on LakeShore 336
        tolerance = Parameter('convergence criterion', FloatRange(0), default=0.1, readonly=False)
        _driving = False
        ...

        def write_target(self, target):
            # reactivate heater in case it was switched off
            self.communicate(f'RANGE {self.loop},{self.heater_range};RANGE?{self.loop}')
            self.communicate(f'SETP {self.loop},{target};*OPC?')
            self._driving = True
            # Setting the status attribute triggers an update message for the SECoP status
            # parameter. This has to be done before returning from this method!
            self.status = BUSY, 'target changed'
            return target
        ...

        def read_status(self):
            code = int(self.communicate(f'RDGST?{self.channel}'))
            if code >= 128:
                text = 'units overrange'
            elif code >= 64:
                text = 'units zero'
            elif code >= 32:
                text = 'temperature overrange'
            elif code >= 16:
                text = 'temperature underrange'
            elif code % 2:
                # ignore 'old reading', as this may happen in normal operation
                text = 'invalid reading'
            elif abs(self.target - self.value) > self.tolerance:
                if self._driving:
                    return BUSY, 'approaching setpoint'
                return WARN, 'temperature out of tolerance'
            else:  # within tolerance: simple convergence criterion
                self._driving = False
                return IDLE, ''
            return ERROR, text


Finally, the config file would be:

``cfg/example_cryo_cfg.py``:

.. code:: python

    Node('example_cryo.psi.ch',  # a globally unique identification
         'this is an example cryostat for the Frappy tutorial',  # describes the node
          interface='tcp://10767')  # you might choose any port number > 1024
    Mod('io',  # the name of the module
        'frappy_psi.lakeshore.LakeshoreIO',  # the class used for communication
        'communication to main controller',  # a description
        uri='serial://COM6:?baudrate=57600+parity=odd+bytesize=7',  # the serial connection
        )
    Mod('T',
        'frappy_psi.lakeshore.TemperatureLoop',
        'Sample Temperature',
        io='io',
        channel='A',  # the channel on the LakeShore for this module
        loop=1,  # the loop to be used
        value=Param(max=470),  # set the maximum expected T
        target=Param(max=420),  # set the maximum allowed target T
        heater_range=3,  # 5 for model 350
        )


Now, you should try again restarting the server and the client, if it works, you have done a good job!
If not, you might need to fix the code first ...


More Complex Configurations
...........................

Without coding any more class, much more complex situations might be realized just by
extending the configuration. Using a single LakeShore controller, you might add more
temperature sensors or (in the case of Model 336 or 350) even a second temperature loop,
just by adding more ``Mod(`` sections to the configuration file. In case more than 4 channels
are needed, an other module ``io2`` has to be added for the second controller and so on.


Appendix 1: The Solution
------------------------

You will find the full solution code via the ``[source]`` link in the automatic
created documentation of the class :class:`frappy_demo.lakeshore.TemperatureLoop`.



.. _lsc_manual_extract:

Appendix 2: Extract from the LakeShore Manual
---------------------------------------------

.. table:: commands used in this tutorial

    ====================== =======================
    **Query Identification**
    ----------------------------------------------
    Command                \*IDN? *term*
    Reply                  <manufacturer>,<model>,<instrument serial>/<option serial>, <firmware version> *term*
    Example                LSCI,MODEL336,1234567/1234567,1.0
    **Query Kelvin Reading for an Input**
    ----------------------------------------------
    Command                KRDG?<input> *term*
    Example                KRDG?A
    Reply                  <kelvin value> *term*
    Example                +273.15
    **Query Input Status**
    ----------------------------------------------
    Command                RDGST?<input> *term*
    Reply                  <status bit weighting> *term*
    Description            The integer returned represents the sum of the bit weighting \
                           of the input status flag bits. A “000” response indicates a valid reading is present.
    Bit / Value            Status
    0 / 1                  invalid reading
    1 / 2                  old reading (Model 340 only)
    4 / 16                 temperature underrange
    5 / 32                 temperature overrange
    6 / 64                 sensor units zero
    7 / 128                sensor units overrange
    **Set Control Loop Setpoint**
    ----------------------------------------------
    Command                SETP <loop>,<value> *term*
    Example                SETP 1,273.15
    **Query Control Loop Setpoint**
    ----------------------------------------------
    Command                SETP?<loop> *term*
    Reply                  <value> *term*
    Example                +273.15
    **Set Heater Range**
    ----------------------------------------------
    Command (340)          RANGE <range number> *term*
    Command (336/350)      RANGE <loop>,<range number> *term*
    Description            0: heater off, 1-5: heater range (Model 336: 1-3)
    **Query Heater Range**
    ----------------------------------------------
    Command (340)          RANGE? *term*
    Command (336/350)      RANGE?<loop> *term*
    Reply                  <range> *term*
    **Operation Complete Query**
    ----------------------------------------------
    Command                \*OPC?
    Reply                  1
    Description            in Frappy, we append this command to request in order
                           to generate a reply
    ====================== =======================
