Reference
---------

Core
....

For convenience everything documented on this page may also be
imported from the frappy.core module.


Module Base Classes
...................

.. _done unique:

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

Access method decorators
........................

.. autofunction:: frappy.rwhandler.nopoll


.. _datatypes:

Datatypes
.........

.. autoclass:: frappy.datatypes.FloatRange
    :members: __call__

.. autoclass:: frappy.datatypes.IntRange
    :members: __call__

.. autoclass:: frappy.datatypes.BoolType
    :members: __call__

.. autoclass:: frappy.datatypes.ScaledInteger
    :members: __call__

.. autoclass:: frappy.datatypes.EnumType
    :members: __call__

.. autoclass:: frappy.datatypes.StringType
    :members: __call__

.. autoclass:: frappy.datatypes.TupleOf
    :members: __call__

.. autoclass:: frappy.datatypes.ArrayOf
    :members: __call__

.. autoclass:: frappy.datatypes.StructOf
    :members: __call__

.. autoclass:: frappy.datatypes.BLOBType
    :members: __call__

.. autoclass:: frappy.datatypes.DataTypeType
    :members: __call__

.. autoclass:: frappy.datatypes.ValueType
    :members: __call__

.. autoclass:: frappy.datatypes.NoneOr
    :members: __call__

.. autoclass:: frappy.datatypes.OrType
    :members: __call__

.. autoclass:: frappy.datatypes.LimitsType
    :members: __call__


Communication
.............

.. autoclass:: frappy.modules.Communicator
    :show-inheritance:
    :members: communicate

.. autoclass:: frappy.io.IOBase
    :show-inheritance:

.. autoclass:: frappy.io.StringIO
    :show-inheritance:
    :members: communicate, multicomm

.. autoclass:: frappy.io.BytesIO
    :show-inheritance:
    :members: communicate, multicomm

.. autoclass:: frappy.io.HasIO
    :show-inheritance:

.. autoclass:: frappy.lib.asynconn.AsynTcp
    :show-inheritance:

.. autoclass:: frappy.lib.asynconn.AsynSerial
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

.. include:: configuration.rst