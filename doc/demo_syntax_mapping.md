## A SECoP Syntax for Demonstration

### Mapping of Messages

Please remind: replies always end with en empty line, which means that there are
2 newline characters at the end of each reply. To emphasize that, in this document
a bare '_' is shown as a replacement for the closing empty line.

#### ListDevices

    > !*
      <device-name1>
      <device-name2>
      ...
      <device-nameN>
      _

#### ListDeviceParams

    > !<device>:*
      <device>:<param1>
      <device>:<param2>
      ...
      <device>:<paramN>
      _

#### ReadRequest

    > <device>:<param>
      <device>:<param1>=<value>
      _

Or, in case it is combined with timestamp (may be also sigma, unit ...). See also
below under "client parameters" / "reply_items".

     > <device>:<param>
       <device>:<param1>=<value>;t=<timestamp>
       _
     > <device>:<param>
       <device>:<param1>=<value>;t=<timestamp>;s=<sigma>
        _
     > <device>:<param>
       <device>:<param1>=<value>;t=<timestamp>;s=<sigma>;unit=<unit>
       _

#### ReadPropertiesOfAllDevices
remark: for shortness the name of the value property and the preceding ':' is omitted

     > *:*:*
       <device1>:<param1>=<value1>
       <device1>:<param1>:<prop2>=<value2>
       ...
       <deviceN>:<paramM>:<propL>=<valueK>
       _

#### ReadPropertiesOfADevice
means read properties of all parameters of a device)

     > <device>:*:*
       <device>:<param1>=<value1>
       <device>:<param1>:<prop2>=<value2>
       ...
       <device>:<paramN>:<propM>=<valueL>
       _

#### ReadPropertiesOfAParameter

     > <device>:<param>:*
       <device>:<param>=<value1>
       <device>:<param>:<prop2>=<value2>
       ...
       <device>:<param>:<propN>=<valueN>
       _

#### ReadSpecificProperty

     > <device>:<param>:<prop>
       <device>:<param>:<prop>=<value>
       _

In case you want the value only, and not the timestamp etc, '.' is a placeholder for the
value property

     > <device>:<param>:.
       <device>:<param>:.=<value>
       _

#### ReadValueNotOlderThan

Instead of this special Request, I propose to make a client parameter "max_age",
which specifies in general how old values may be to be returned from cache.

#### Write

remark: writes to other than the 'value' property are not allowed. If anyone sees a
reasonable need to make writeable properties, a WriteProperty Request/Reply should
be discussed

    > <device>:<param>=<value>
      <device>:<param>=<readback-value>
      _

#### Command

If we want to distinguish between a write request and a command, we need also a
different syntax. It is to decide, how arguments may be structured / typed.
Should a command also send back a "return value"?

    > <device>:<param> <arguments>
      <device>:<param> <arguments>
      _

#### Error replies

Error reply format:

      ~<error-specifier>~ <path or other info>
      _

The error-specifier should be predefined identifer.

    > tempature:target
      ~NoSuchCommand~ tempature
      _

    > temperature:taget
      ~NoSuchParameter~ temperature:taget
      _

#### FeatureListRequest

Instead of an extra FeatureListRequest message, I propose to do have a device,
which contains some SEC node properties, with information about the SEC node,
and client parameters, which can be set by the ECS for optional
features. Remind that internally the SEC Node has to store the client parameters
separately for every client.

#### SEC Node properties

You are welcome to propose better names:

    > ::implements_timestamps
      ::implements_timestamps=1
      _
    > ::implements_async_communication
      ::implements_async_communication=1
      _

The maximum time delay for a response from the SEC Node:

    > ::reply_timeout=10
      ::reply_timeout=10
      _

SEC Node properties might be omitted for the default behaviour.

#### Client parameters

Enable transmission of timestamp and sigma with every value

    > :reply_items=t,s
      :reply_items=t,s
      _

If a requested property is not present on a parameter, it is just omitted in the reply.

The reply_items parameter might be not be present, when the SEC node does not implement
timestamps and similar.

Update timeout (see Update message)

    > :update_timeout=10
      :update_timeout=10

#### SubscribeToAsyncData

In different flavors: all parameters and all devices:

    > +*:*
      <device1>.<param1>
      ...
      <deviceN>.<paramM>
      _

Only the values of all devices:

    > +*
      +<device1>
      ...
      +<deviceN>
      _

All parameters of one device:

    > +<device>:*
      +<device>:<param1>
      ...
      +<device>:<paramN>
      _

I think we need no special subscriptions to properties, as :reply_items should be
recognized by the updates. All other properties are not supposed to be changed during
an experiment (we might discuss this).

If an Unsubscribe Message would be implemented, it could be start with a '-'

#### Update

In order to stick to a strict request / reply mechanism I propose instead of a real
asynchronous communication to have an UpdateRequest. The reply of an UpdateRequest
might happen delayed.

- it replies immediately with a list of all subscripted updates, if some happend since
  the last UpdateRequest
- if nothing has changed, the UpdateReply is sent as soon as any update happens
- if nothing happens within the time specified by :update_timeout
  an empty reply is returned.

If a client detects no reply within :update_timeout plus ::reply_timeout,
it can assume the the SEC Node is dead.

The UpdateRequest may be just an empty line (my favorite) or, if you prefer an
question mark:

    > ?
      <device1>=<value1>
      <device2>.<paramX>=<value2>
      _

With no update during :update_timeout seconds, the reply would be

    > ?
      _


#### Additional Messages

I list here some additional messages, which could be useful, but wich were not yet
identified as special messages. They all follow the same syntax, which means that
it is probably no extra effort for the implementation.

Interestingly, we have defined ReadPropertiesOfAllDevices, but not Read a specific
property of all parameters. At least reading the value properties is useful:

     > *:*

List all device classes (assuming a device property "class")

     > *::class
       <device1>::class=<class1>
       <device2>::class=<class2>
       ...
       <deviceN>::class=<classN>
       _

The property meaning is for saying: this device is important for the experimentalist,
and has the indicated meaning. It might be used by the ECS to skip devices, which
are of no interest for non experts. Example:

     > *::meaning
       ts::meaning=sample temperature
       mf::meaning=magnetic field
       _

We might find other useful messages, which can be implemented without any additional
syntax.


#### A possible syntax extension:

Allow a comma separated list for path items:

    > ts,mf
      ts=1.65
      mf=5.13
      _

    > ts::.,t,s
      ts=<value>
      ts::t=<timestamp>
      ts::s=<sigma>
      _

If somebody does not like the :reply_items mechanism, we could us the latter example
as alternative for reading values together with timestamp and sigma.
