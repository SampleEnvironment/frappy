Introduction
============

Frappy - a Python Framework for SECoP
-------------------------------------

*Frappy* is a Python framework for creating Sample Environment Control Nodes (SEC Node) with
a SECoP interface. A *SEC Node* is a service, running usually a computer or microcomputer,
which accesses the hardware over the interfaces given by the manufacturer of the used
electronic devices. It provides access to the data in an abstracted form over the SECoP interface.
`SECoP <https://github.com/SampleEnvironment/SECoP/tree/master/protocol>`_ is a protocol for
communicating with Sample Environment and other mobile devices, specified by a committee of
the `ISSE <https://sampleenvironment.org>`_.

The Frappy framework deals with all the details of the SECoP protocol, so the programmer
can concentrate on the details of accessing the hardware with support for different types
of interfaces (TCP or Serial, ASCII or binary). However, the programmer should be aware of
the basic principle of the SECoP protocol: the hardware abstraction.


Hardware Abstraction
--------------------

The idea of hardware abstraction is to hide the details of hardware access from the SECoP interface.
A SECoP module is a logical component of an abstract view of the sample environment.
It is one independent value of measurement like a temperature or pressure or a physical output like
a current or voltage. This corresponds roughly to an EPICS channel or a NICOS device. On the
hardware side we may have devices with several channels, like a typical temperature controller,
which will be represented individual SECoP modules.
On the other hand a SECoP channel might be linked with several hardware devices, for example if
you imagine a superconducting magnet controller built of separate electronic devices like a power
supply, switch heater and coil temperature monitor. The latter case does not mean that we have
to hide the details in the SECoP interface. For an expert it might be useful to give at least
read access to hardware specific data by providing them as separate SECoP modules. But the
magnet module should be usable without knowledge of all the inner details.

A SECoP module has:

* **properties**: static information describing the module, for example a human readable
  *description* of the module or information about the intended *visibility*.
* **parameters**: changing information about the state of a module (for example the *status*
  containing information about the state of the module) or modifiable information influencing
  the measurement (for example a "ramp" rate).
* **commands**: actions, for example *stop*.

A SECoP module belongs to an interface class, mainly *Readable* or *Drivable*. A *Readable*
has at least the parameters *value* and *status*, a *Drivable* in addition *target*. *value* is
the main value of the module and is read only. *status* is a tuple (status code, status text),
and *target* is the target value. When the *target* parameter value of a *Drivable* changes,
the status code changes normally to a busy code. As soon as the target value is reached,
the status code changes back to an idle code, if no error occurs.

**Programmers Hint:** before starting to code, choose carefully the main SECoP modules you want
to provide to the user.


Programming a Driver
--------------------

:ref:`Programming a driver <class_coding>`  means:

- selecting a base class to be extended (e.g. :class:`frappy.modules.Readable`
  or :class:`frappy.modules.Drivable`).
- defining the parameters
- coding the methods to retrieve and access these parameters


Support for Communication with the Hardware
-------------------------------------------

Often the access to the hardware has to be done over a serial communication over LAN,
RS232 or USB. The mixin :class:`frappy.io.HasIO` and the classes :class:`frappy.io.StringIO`
and :class:`frappy.io.BytesIO` have all the functionality needed for this.

Some hardware also requires calls to libraries offered by the manufacturers, certainly this
is also possible. In case there is no python package for this, but a C/C++ API, you might
use one of the following:

- ``Ctypes (A foreign function library for Python) <https://docs.python.org/3/library/ctypes.html>``
- ``CFFI (C Foreign Function Interface for Python) <https://cffi.readthedocs.io/>``
- ``Extending Python with C or C++ <https://docs.python.org/3/extending/extending.html>``


.. TODO: shift this to an extra section


