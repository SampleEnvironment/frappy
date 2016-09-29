Simple communication protocol
=============================
| *Version 0.0.2*
| *Copyright 2012: Alexander Lenz, Dr. Enrico Faulhaber*


Table of contents
-----------------

.. contents::
.. sectnum::

Disambiguation
--------------

Device
''''''
A device is a logical part of the complete system. This may be any piece of hardware which
can be accessed seperately. Also a logical axis, implemented with multiple motors can be a device.

Parameter
'''''''''
A parameter is a device depended value which represents (usually) a physical value.
It can be read only or read-/writeable.

Messages
--------

The messages are devided into commands and responses.

A command consists of the device of interest, the relevant parameter, an operator
that specifies what should happen, and a value if neccessary.

::

    Commands:       <device>/<parameter><operator><value_if_any>\n

You will get a response for each command (\ **even if it failed!**\ ).
These reponses consist of an error code, the mirrored command (to verify for what command the response is related)
and a value if requested.

::

    Response:       <error_code> <mirrored_command><value_if_any>\n


For limitations regarding the message contents, have a look at: `Limitations`_



Operators
---------

? (Request)
'''''''''''
    This operator can be used to request data.
    In the most cases, you want to request the value of device parameter:

    **Command**
    ::

        <device>/<parameter>?\n

    **Response**
    ::

        <error_code> <device>/<parameter>=<value_if_success>\n

= (Set)
'''''''
    This operator can be used to write a device value.

    **Command**
        ::

                <device>/<parameter>=<value>\n

        **Response**
        ::

                <error_code> <device>/<parameter>=<value>\n


Protocol error codes
--------------------

In case of an error, you get the following response:

::

    <error_code> <mirrored_command>


The following errors describe errors of the protocol, not the device.

======================= ==============
**Error**               **Error code**
======================= ==============
No error                0
Unknown error           1
Connection error        2
Command unknown         3
Device unknown          4
Parameter unknown       5
Format error            6
Value out of limits     7
Param not writable      8
Not allowed             9
======================= ==============

Device stati
------------

The following status codes describe the device status and can be requested via:

::

    <device>/status:\n


==========  ===========
**Status**  **Meaning**
==========  ===========
IDLE        Device is alive and ready to accept commands.
BUSY        Device is performing some action and therefore busy. It doesn't accept new commands. All Parameters can be read.
ERROR       Something bad happened, a manual action is required. Some command could unexpectedly not be performed.
UNKNOWN     Unknown device state.
==========  ===========


Limitations
-----------

Naming & Formatting
'''''''''''''''''''

- Device names are all lower case and can consist of letters, numbers and underscores (no whitespace!).
- Device names consist of up to 80 characters.
- Parameter names are all lower case and can consist of letters, numbers and underscores (no whitespace!).
- Parameter names consist of up to 80 characters.
- Floating point numbers are using a decimal point (5.23).
- Lists are commma-separated and enclosed by square brackets ([entry1,entry2,entry3]).
- Strings are enclosed by single ticks ('str').
- Messages consist of up to 256 characters.

Devices
'''''''

General
"""""""
All devices have to support at least the following parameters:

    **status**
        This **read only** parameters describes the current device state.
        It contains a list with two items.

            1. A short constant status string (Have a look at: `Device stati`_)
            2. A longer description which can contain any character except a comma!

    **parameters**
        This **read only** parameter represents a list of all available parameters of the given device.
        It contains a comma seperated list with all parameter names.

Readable
""""""""
All devices which provide any type of readable value have to support the general parameters and at leas the following:
    **value**
        This **read only** parameter represents the current 'main value'.
        It contains a single value which can be a float or integer number, or a string.

Writable
""""""""
All devices for which you can set a value have to support at least the general parameters, all parameters of `Readable`_ devices and the following:
    **target**
        This **read/write** parameter represents the device's target value.
        It contains a single value which can be a float or integer number, or a string.
        If you set the target value, the device goes into 'BUSY' state and tries to reach that value.
        The current value can be requested by the 'value' parameter.

Server device
"""""""""""""
        The server have to provide a device for direct communication with the protocol server.
        It has to provide at least the parameters of a general device (`Devices`_) plus the following:

        **devices**
            A list of all available devices.
        **version**
            A version string which identifies the protocol version, the server implements.

        The server device can be queried by omitting the <device> parameter (+ the '/').
        ::

            devices?\n
            version?\n


Examples
--------

Let's have a look at some examples:

+---------------+---------------------------------+
|**Device:**    |temp_ctrl                        |
+---------------+---------------------------------+
|**Type:**      |Temperature controller (Moveable)|
+---------------+---------------------------------+
|**Parameters:**| - status **(mandatory)**        |
|               | - parameters **(mandatory)**    |
|               | - value **(mandatory)**         |
|               | - target **(mandatory)**        |
|               | - ...                           |
+---------------+---------------------------------+

Requesting the current setpoint (target)
''''''''''''''''''''''''''''''''''''''''

    **Command**

        ::

            temp_ctrl/target?\n

    **Response**

        ::

            0 temp_ctrl/target=0.42\n

Setting the setpoint (target)
'''''''''''''''''''''''''''''

        **Command**

                ::

                        temp_ctrl/target=0.21\n

        **Response**

                ::

                        0 temp_ctrl/target=0.21\n

Setting an out-of-bounds setpoint (target)
''''''''''''''''''''''''''''''''''''''''''

        **Command**

                ::

                        temp_ctrl/target=-7.5\n

        **Response**

                ::

                        7 temp_ctrl/target=-7.5\n


Requesting the status
'''''''''''''''''''''

        **Command**

                ::

                        temp_ctrl/status?\n

        **Response**

                ::

                        0 temp_ctrl/status=BUSY,I'm ramping!\n

Requesting the device list
''''''''''''''''''''''''''

        **Command**

                ::

                        /devices?\n

        **Response**

                ::

                        0 /devices=temp_ctrl,another_dev1,another_dev2\n

..  Allowed extensions
    ------------------

    Additional operators
    ''''''''''''''''''''

    \* (Wildcard)
    """""""""""""
        This operator is a little more advanced than the others.
        It represents a wild card and can be combined with other operators.
        The response you will get, are multiple messages which contain:
        ::

            <error_code> <the_mirrored_command> <answer_for_the_operator>

        If you want to request all parameters of a device, it will be:

        **Command**
        ::

                <device>/*?\n

        **Response**
        *Multiple*
        ::

                <error_code> <device>/*? <device>/<parameter>=<value>\n

    Examples
    ^^^^^^^^
    Requesting all parameters
    *************************

        **Command**

            ::

                temp_ctrl/*?\n

        **Response**
            ::

                0 temp_ctrl/*? temp_ctrl/status=BUSY,I'm ramping!\n
                0 temp_ctrl/*? temp_ctrl/parameters=status,parameters,value,target\n
                0 temp_ctrl/*? temp_ctrl/value=0.21\n
                0 temp_ctrl/*? temp_ctrl/target=0.42\n

Recommendations
---------------
Interfaces
''''''''''

We provide some recommendations for the interface configuration when using the simple communication protocol:

Serial (RS232)
""""""""""""""

If you are using a serial connection, you should use the following configuration:

=============   ==============
**Baudrate**    9600 or 115200
**Data bits**   8
**Parity**      None
**Stop bits**   1
=============   ==============

Network (TCP)
"""""""""""""

If you are using a TCP based network connection, you should use the following configuration:

========    =====
**Port**    14728
========    =====

Network (UDP)
"""""""""""""

We recommend not to use UDP connections at all, as the protocol was not designed for such connections.




