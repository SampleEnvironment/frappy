Frappy Internals
----------------

Frappy is a powerful framework, which does everything behind the
scenes you need for getting a SEC node to work. This section describes
what the framwork does for you.

Startup
.......

On startup several methods are called. First :meth:`earlyInit` is called on all modules.
Use this to initialize attributes independent of other modules, if you can not initialize
as a class attribute, for example for mutable attributes.

Then :meth:`initModule` is called for all modules.
Use it to initialize things related to other modules, for example registering callbacks.

After this, :meth:`startModule` is called with a callback function argument.
:func:`frappy.modules.Module.startModule` starts the poller thread, calling
:meth:`writeInitParams` for writing initial parameters to hardware, followed
by :meth:`initialReads`. The latter is meant for reading values from hardware,
which are not polled continuously. Then all parameters configured for poll are polled
by calling the corresponding read_*() method. The end of this last initialisation
step is indicated to the server by the callback function.
After this, the poller thread starts regular polling, see next section.

When overriding one of above methods, do not forget to super call.


.. _polling:

Polling
.......

By default, a module inheriting from :class:`Readable <frappy.modules.Readable>` is
polled every :attr:`pollinterval` seconds. More exactly, the :meth:`doPoll`
method is called, which by default calls :meth:`read_value` and :meth:`read_status`.

The programmer might override the behaviour of :meth:`doPoll`, often it is wise
to super call the inherited method.

:Note:

    Even for modules not inheriting from :class:`Readable <frappy.modules.Readable>`,
    :meth:`doPoll` is called regularly. Its default implementation is doing nothing,
    but may be overridden to do customized polling.

In addition, the :meth:`read_<param>` method is called every :attr:`slowinterval`
seconds for all parameters, in case the value was not updated since :attr:`pollinterval`
seconds.

The decorator :func:`nopoll <frappy.rwhandler.nopoll>` might be used on a :meth:`read_<param>`
method in order to indicate, that the value is not polled by the slow poll mechanism.


.. _client notification:

Client Notification
...................

Whenever a parameter is changed by assigning a value to the attribute or by
means of the access method, an ``update`` message is sent to all activated clients.
Frappy implements the extended version of the ``activate`` message, where single modules
and parameters might be activated.


.. _type check:

Type check and type conversion
..............................

Assigning a parameter to a value by setting the attribute via ``self.<param> = <value>``
or ``<module>.<param> = <value>`` involves a type check and possible a type conversion,
but not a range check for numeric types. The range check is only done on a ``change``
message.


TODO: error handling, logging
