Reference
---------

Module Base Classes
...................

.. autodata:: frappy.modules.Done

.. autoclass:: frappy.modules.Module
    :members: earlyInit, initModule, startModule

.. autoclass:: frappy.modules.Readable
    :members: Status

.. autoclass:: frappy.modules.Writable

.. autoclass:: frappy.modules.Drivable
    :members: Status, isBusy, isDriving, stop


Parameters, Commands and Properties
...................................

.. autoclass:: frappy.params.Parameter
.. autoclass:: frappy.params.Command
.. autoclass:: frappy.properties.Property
.. autoclass:: frappy.modules.Attached
    :show-inheritance:


Datatypes
.........

.. autoclass:: frappy.datatypes.FloatRange
.. autoclass:: frappy.datatypes.IntRange
.. autoclass:: frappy.datatypes.BoolType
.. autoclass:: frappy.datatypes.ScaledInteger
.. autoclass:: frappy.datatypes.EnumType
.. autoclass:: frappy.datatypes.StringType
.. autoclass:: frappy.datatypes.TupleOf
.. autoclass:: frappy.datatypes.ArrayOf
.. autoclass:: frappy.datatypes.StructOf
.. autoclass:: frappy.datatypes.BLOBType



Communication
.............

.. autoclass:: frappy.modules.Communicator
    :show-inheritance:
    :members: communicate

.. autoclass:: frappy.io.StringIO
    :show-inheritance:
    :members: communicate, multicomm

.. autoclass:: frappy.io.BytesIO
    :show-inheritance:
    :members: communicate, multicomm

.. autoclass:: frappy.io.HasIO
    :show-inheritance:

.. autoclass:: frappy.rwhandler.ReadHandler
    :show-inheritance:
    :members:

.. autoclass:: frappy.rwhandler.CommonReadHandler
    :show-inheritance:
    :members:

.. autoclass:: frappy.rwhandler.WriteHandler
    :show-inheritance:
    :members:

.. autoclass:: frappy.rwhandler.CommonWriteHandler
    :show-inheritance:
    :members:


Exception classes
.................

.. automodule:: frappy.errors
    :members:

.. include:: server.rst

