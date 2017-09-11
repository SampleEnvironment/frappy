SECoP Messages
==============

All Messages are formatted in the same way:
  &lt;keyword&gt;[&lt;space&gt;&lt;specifier&gt;[&lt;space&gt;&lt;JSON_formatted_data&gt;]]&lt;linefeed&gt;

where [] enclose optional parts. This basically results in 3 different possible
formattings:

  * type A: "keyword\n"
  * type B: "keyword specifier\n"
  * type C: "keyword specifier JSON_data\n"

Note: numerical values and strings appear 'naturally' formatted in JSON, i.e. 5.0 or "a string"

&lt;keyword&gt; is one of a fixed list of defined keywords, &lt;specifier&gt; is either the
name of the module optionally followed by ':' + the name of a command or parameter,
or one of a fixed list of predefined keywords, depending on the message keyword.

At the moment it is considered syntactic sugar to omit the parametername in a request.
In replies the SEC-node (in the playground) will always use the correct parameter.
On change-requests the parameter is assumed to be 'target', on trigger-requests it is assumed to be 'value'.
Clients should not rely on this and explicitly state the parametername!

All names and keywords are defined to be identifiers in the sense, that they are not longer than 63 characters and consist only of letters, digits and underscore and do not start with a digit. (i.e. T_9 is ok, whereas t{9} is not!)
No rule is without exception, there is exactly ONE special case: the identify request consists of the literal string '*IDN?\n' and its answer is formatted like an valid SCPI response for *IDN?.

We rely on the underlying transport to not split messages, i.e. all messages are transported as a whole and no message interrupts another.

Also: each client MUST at any time correctly handle incoming event messages, even if it didn't activate them!

Implementation node:
Both SEC-node and ECS-client can close the connection at any time!


List of Intents/Actions:
------------------------

  * Identify -&gt; Ident
  * Describe -&gt; Description
  * Activate Events -&gt; initial data transfer -&gt; end-of-transfer-marker
  * Deactivate Async Events -&gt; confirmation
  * Command &lt;module&gt;:&lt;command&gt; -&gt; confirmation -&gt; result_event
  * Heartbeat &lt;nonce&gt; -&gt; Heartbeat_reply
  * Change &lt;module&gt;[:&lt;param&gt;] JSON_VALUE -&gt; confirmation -&gt; readback_event
  * TRIGGER &lt;module&gt;[:&lt;param&gt;] -&gt; read_event

At any time an Event may be replied. Each request may also trigger an Error.

Line-ending is \lf.
\cr is ignored and never send.
Warning: One Message per line: Description line can be looooong!!!


Allowed combinations as examples:
(replace &lt;..&gt; with sensible stuff)


Identify
--------

  * Request: type A: '*IDN?'
  * Reply:   special: 'SECoP, SECoPTCP, V2016-11-30, rc1'
  * queries if SECoP protocol is supported and which version it is
  Format is intentionally choosen to be compatible to SCPI (for this query only).
  It is NOT intended to transport information about the manufacturer of the hardware, but to identify this as a SECoP device and transfer the protocol version!


Describe
--------

  * Request: type A: 'describe'
  * Reply:   type C: 'describing &lt;ID&gt; {"modules":{"T1":{"baseclass":"Readable", ....'
  * request the 'descriptive data'. The format needs to be better defined and
  may possibly just follow the reference implementation.
  &lt;ID&gt; identifies the equipment. It should be unique. Our suggestion is to use something along &lt;facility&gt;_&lt;id&gt;, i.e. MLZ_ccr12 or PSI_oven4.


Activate Async Events
---------------------

  * Request: type A: 'activate'
  * Reply:   several EVENT lines (initial value transfer) followed by: type A: 'active'
  * Activates sending of Async Events after transferring all live quantities once
  and an 'end-of-initial-transfer' marker. After this events are enabled.


Deactivate Async Events
-----------------------

  * Request: type A: 'deactivate'
  * Reply:   type A: 'inactive'
  * Deactivate sending of async Events. A few events may still be on their way until the 'inactive' message arrives.


Execute Command
---------------

  * Request: type B: 'do &lt;module&gt;:&lt;command&gt;' for commands without arguments
  * Request: type C: 'do &lt;module&gt;:&lt;command&gt; JSON_argument' for commands with arguments
  * Reply:   type C: 'done &lt;module&gt;:&lt;command&gt; JSON_result' after the command finished
  * start executing a command. When it is finished, the reply is send.
    The JSON_result is the a list of all return values (if any), appended with qualifiers (timestamp)


Write
-----

  * Request: type C: 'change &lt;module&gt;[:&lt;param&gt;] JSON_value'
  * Reply: type C: 'changed &lt;module&gt;:&lt;param&gt; JSON_read_back_value'
  * initiate setting a new value for the module or a parameter of it.
  Once this is done, the read_back value is confirmed by the reply.


Trigger
-------

  * Request: type B: 'read &lt;module&gt;[:&lt;param&gt;]'
  * Reply:   None directly. However, one Event with the read value will be send.
  * Read the requested quantity and sends it as an event (even if events are disabled or the value is not different to the last value).


Heartbeat
---------

  * Request: type A: 'ping'
  * Request: type B: 'ping &lt;nonce&gt;'
  * Reply:   type A: 'pong'
  * Reply:   type B: 'pong &lt;nonce&gt;'
  * Replies the given argument to check the round-trip-time or to confirm that the connection is still working.
  &lt;nonce&gt; may not contain &lt;space&gt;. It is suggested to limit to a string of up to 63 chars consisting of letters, digits and underscore not beginning with a digit. If &lt;nonce&gt; is not given (Type A), reply without it.


EVENT
-----

Events can be emitted any time from the SEC-node (except if they would interrupt another message).

  * Request: None. Events can be requested by Trigger or by Activating Async Mode.
  * Reply:   type C: 'event &lt;module&gt;:&lt;param&gt; JSON_VALUE'
  * Informs the client that a parameter got changed its value.
  In any case the JSON_value contain the available qualifiers as well:
    * "t" for the timestamp of the event.
    * "e" for the error of the value.
    * "u" for the unit of the value, if deviating from the descriptive data
    * further qualifiers, if needed, may be specified.
  The qualifiers are a dictionary at position 2 of a list, where the value occupies position 1.
  This holds true also for complex datatypes (of value)!

  examples:

  * 'update T1:value [3.479, {"t":"149128925.914882", "e":0.01924}]
  * 'update T1:p [12, {"t":"149128927.193725"}]'
  * 'update Vector:value [[0.01, 12.49, 3.92], {"t":"149128925.914882"}]'


ERROR
-----

  * Request: None. can only be a reply if some request fails.
  * Reply: type C: 'ERROR &lt;errorclass&gt; JSON_additional_stuff'
  * Following &lt;errorclass&gt; are defined so far:
    * NoSuchDevice: The action can not be performed as the specified device is non-existent.
    * NoSuchParameter: The action can not be performed as the specified parameter is non-existent.
    * NoSuchCommand: The specified command does not exist.
    * CommandFailed: The command failed to execute.
    * CommandRunning: The command is already executing.
    * ReadOnly: The requested write can not be performed on a readonly value..
    * BadValue: The requested write or Command can not be performed as the value is malformed or of wrong type.
    * CommunicationFailed: Some communication (with hardware controlled by this SEC-Node) failed.
    * IsBusy: The reequested write can not be performed while the Module is Busy
    * IsError: The requested action can not be performed while the module is in error state.
    * Disabled: The requested action can not be performed at the moment. (Interlocks?)
    * SyntaxError: A malformed Request was send
    * InternalError: Something that should never happen just happened.
  The JSON part should reference the offending request and give an explanatory string.

  examples:

  * 'ERROR Disabled ["change", "V15", "on", "Air pressure too low to actuate the valve.", {"exception":"RuntimeException","file":"devices/blub/valve.py", "line":13127, "frames":[...]}]'
  * 'ERROR NoSuchDevice ["read","v19", "v19 is not configured on this SEC-node"]'
  * 'ERROR SyntaxError "meas:Volt?"


Examples
--------

(client connects):
(client)    '*IDN?'
(SEC-node)  'Sine2020WP7.1&ISSE, SECoP, V2016-11-30, rc1'
(client)    'describe'
(SEC-node)  'describing SECoP_Testing {"modules":{"T1":{"baseclass":"Readable", ...
(client)    'activate'
(SEC-node)  'update T1 [3.45,{"t":"149128925.914882","e":0.01924}]'
...
(SEC-node)  'active'
(SEC-node)  'update T1 [3.46,{"t":"149128935.914882","e":0.01912}]'
(client)    'ping fancy_nonce_37'
(SEC-node)  'pong fancy_nonce_37'
(SEC-node)  'update T1 [3.49,{"t":"149128945.921397","e":0.01897}]'
...

