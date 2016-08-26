## A SECoP Syntax for Demonstration

I feel it is very hard to explain in a talk what we are talking
about when discussing the concepts of SECoP. Would it not be easier
with an example syntax and an example SEC node? That is why I
created a simple syntax, which is on one hand easily understandable
by humans and on the other hand fulfills the requirements for a real syntax.

### An Example of an SEC Node with the Demo Syntax

We have 2 main devices: sample temperature and magnetic field.

    > ts
      ts=9.887

    > mf
      mf=5.1


We have some additional devices, coil temperature of upper and lower coil.

    > tc1
      tc1=2.23

    > tc2
      tc2=2.311

When we use the term "device" here, we do not mean a device in the sense of a
cryomagnet or a furnace. For SECoP, roughly any physical quantity which may
be of interest to the experimentalist, is its own device.


We can use wildcards to see the values of all devices at once.

    > *
      ts=9.887
      mf=5.1
      tc1=2.23
      tc2=2.311
      label='Cryomagnet MX15; at 9.887 K; Persistent at 5.1 Tesla'


The "> " is not part of the syntax, it is just indicating the request.
A request is always one line.
A reply might contain several lines and always ends with an empty line.

The last device here is a text displayed on the SE computer. It may not be
very useful, but it demonstrates that a device value may also be a text.

A device has parameters. The main parameter is its value. The value parameter
is just omitted in the path. We can list the the parameters and its values
with the following command:

    > mf:*
      mf=5.13
      mf:status=0
      mf:target=14.9
      mf:ramp=0.4
      mf:set_point=5.13
      mf:persistent_mode=0
      mf:switch_heater=1

If we want to change the field we have to set its target value:

    > mf:target=12
      mf:target=12.0

    > mf:*
      mf=5.13
      mf:status=1
      mf:target=12.0
      mf:ramp=0.4
      mf:set_point=5.13
      mf:persistent_mode=0
      mf:switch_heater=1

The status is indicating the state of the device. 0 means idle, 1 means busy
(running to the target).

A parameter has properties. The 'value' property is implicit, its just
omitted in the path:

    > mf:status:*
      mf:status=0
      mf:status:value_names=0:idle,1:busy,2:error
      mf:status:type=int
      mf:status:t=2016-08-23 14:55:45.254348

Please notice the property "value_names" indicating the meaning of the status
values.

    > mf:target:*
      mf:target=12.0
      mf:target:writable=1
      mf:target:unit=T
      mf:target:type=float
      mf:target:t=2016-08-23 14:55:44.658749

The last property 't' is the timestamp. If the client want to record timestamps,
it can enable it for all device or parameter readings:

    > :reply_items=t
      :reply_items=t

    > *
      ts=9.867;t=2016-08-23 14:55:44.655862
      mf=5.13;t=2016-08-23 14:55:44.656032
      tc1=2.23;t=2016-08-23 14:55:44.656112
      tc2=2.311;t=2016-08-23 14:55:44.656147
      label='Cryomagnet MX15; at 9.867 K; Ramping at 5.13 Tesla';t=2016-08-23 14:55:44.656183

There is also a list command showing the devices (and parameters) without
values. I am not sure if we really need that, as we can just use a wildcard
read command and throw away the values.

    > !*
      ts
      mf
      tc1
      tc2
      label

    > !ts:*
      ts
      ts:status
      ts:target
      ts:ramp
      ts:use_ramp
      ts:set_point
      ts:heater_power
      ts:raw_sensor

The property "meaning" indicates the meaning of the most important devices.
We can list all the devices which have a "meaning" property

    > *::meaning
      ts::meaning=temperature
      mf::meaning=magnetic_field

> Markus: We have more things to tell here.


As a last example: the ultimate command to get everything:

    > *:*:*
      ts=9.887
      ts::meaning=temperature
      ts::unit=K
      ts::description='VTI sensor (15 Tesla magnet)\ncalibration: X28611'
      ts::type=float
      ts::t=2016-08-23 14:55:44.655862
      ts:status=0
      ts:status:type=int
      ts:status:t=2016-08-23 14:55:44.655946
      ts:target=10.0
      ts:target:writable=1
      ts:target:unit=K
      ts:target:type=float
      ts:target:t=2016-08-23 14:55:44.655959
      ts:ramp=0.0
      ts:ramp:writable=1
      ts:ramp:unit=K/min
      ts:ramp:type=float
      ts:ramp:t=2016-08-23 14:55:44.655972
      ts:use_ramp=0
      ts:use_ramp:type=int
      ts:use_ramp:t=2016-08-23 14:55:44.655984
      ts:set_point=10.0
      ts:set_point:unit=K
      ts:set_point:type=float
      ts:set_point:t=2016-08-23 14:55:44.655995
      ts:heater_power=0.154
      ts:heater_power:unit=W
      ts:heater_power:type=float
      ts:heater_power:t=2016-08-23 14:55:44.656006
      ts:raw_sensor=1876.3
      ts:raw_sensor:unit=Ohm
      ts:raw_sensor:type=float
      ts:raw_sensor:t=2016-08-23 14:55:44.656018
      mf=5.13
      mf::meaning=magnetic_field
      mf::unit=T
      mf::description=magnetic field (15 Tesla magnet)
      mf::type=float
      mf::t=2016-08-23 14:55:44.656032
      mf:status=0
      mf:status:type=int
      mf:status:t=2016-08-23 14:55:44.656044
      mf:target=12.0
      mf:target:writable=1
      mf:target:unit=T
      mf:target:type=float
      mf:target:t=2016-08-23 14:55:44.658749
      mf:ramp=0.4
      mf:ramp:writable=1
      mf:ramp:unit=T/min
      mf:ramp:type=float
      mf:ramp:t=2016-08-23 14:55:44.656066
      mf:set_point=5.13
      mf:set_point:unit=T
      mf:set_point:type=float
      mf:set_point:t=2016-08-23 14:55:44.656077
      mf:persistent_mode=0
      mf:persistent_mode:type=int
      mf:persistent_mode:t=2016-08-23 14:55:44.656088
      mf:switch_heater=1
      mf:switch_heater:type=int
      mf:switch_heater:t=2016-08-23 14:55:44.656099
      tc1=2.23
      tc1::unit=K
      tc1::description='top coil (15 Tesla magnet)\ncalibration: X30906'
      tc1::type=float
      tc1::t=2016-08-23 14:55:44.656112
      tc1:status=0
      tc1:status:type=int
      tc1:status:t=2016-08-23 14:55:44.656123
      tc1:raw_sensor=5434.0
      tc1:raw_sensor:unit=Ohm
      tc1:raw_sensor:type=float
      tc1:raw_sensor:t=2016-08-23 14:55:44.656134
      tc2=2.311
      tc2::unit=K
      tc2::description='bottom coil (15 Tesla magnet)\ncalibration: C103'
      tc2::type=float
      tc2::t=2016-08-23 14:55:44.656147
      tc2:status=0
      tc2:status:type=int
      tc2:status:t=2016-08-23 14:55:44.656159
      tc2:raw_sensor=4834.5
      tc2:raw_sensor:unit=Ohm
      tc2:raw_sensor:type=float
      tc2:raw_sensor:t=2016-08-23 14:55:44.656169
      label='Cryomagnet MX15; Ramping'
      label::writable=1
      label::type=string
      label::t=2016-08-23 14:55:44.656183
      .:reply_items=t
      .:reply_items:writable=1
      .:reply_items:type=string
      .:reply_items:t=2016-08-23 14:55:44.659617
      .:compact_output=0
      .:compact_output:writable=1
      .:compact_output:type=int
      .:compact_output:t=2016-08-23 14:55:44.656219


The last device '.' is a dummy device to hold the parameters of a client
connection. Changing these parameters must not affect other client connections.
The experimental parameter compact_output is for compressing the result of
wildcard requests: unchanged device and parameter names are omitted.


    > :compact_output=1
      .:compact_output=1

    > *:*:*
      ts=9.887
      ::meaning=temperature
      ::unit=K
      ::description='VTI sensor (15 Tesla magnet)\ncalibration: X28611'
      ::type=float
      ::t=2016-08-23 15:04:55.180514
      :status=0
      ::type=int
      ::t=2016-08-23 15:04:55.180587
      :target=10.0
      ::writable=1
      ::unit=K
      ::type=float
      ::t=2016-08-23 15:04:55.180594
      :ramp=0.0
      ::writable=1
      ::unit=K/min
      ::type=float
      ::t=2016-08-23 15:04:55.180599
      :use_ramp=0
      ::type=int
      ::t=2016-08-23 15:04:55.180604
      :set_point=10.0
      ::unit=K
      ::type=float
      ::t=2016-08-23 15:04:55.180609
      :heater_power=0.154
      ::unit=W
      ::type=float
      ::t=2016-08-23 15:04:55.180615
      :raw_sensor=1876.3
      ::unit=Ohm
      ::type=float
      ::t=2016-08-23 15:04:55.180620
      mf=5.13
      ::meaning=magnetic_field
      ::unit=T
      ::description=magnetic field (15 Tesla magnet)
      ::type=float
      ::t=2016-08-23 15:04:55.180626
      :status=0
      ::type=int
      ::t=2016-08-23 15:04:55.180632
      :target=14.9
      ::writable=1
      ::unit=T
      ::type=float
      ::t=2016-08-23 15:04:55.180637
      :ramp=0.4
      ::writable=1
      ::unit=T/min
      ::type=float
      ::t=2016-08-23 15:04:55.180642
      :set_point=5.13
      ::unit=T

      ...


