
(Outdated!)

Struktur der Messages
=====================

Es gibt folgende Messagetypen:

  * LIST (listet namen einer Ebene auf)
  * READ+WRITE (addressiert einen spezifischen Wert)
  * FETCH (kombiniert LIST+READ, antwort ist multi)
  * COMMAND (um Befehle aufzurufen: stop(), init(),...)
  * (UN)SUBSCRIBE (bucht events, bestellt sie ab, f&uuml;r devices/params)
  * EVENT (ASYNC!)
  * ERROR
  * POLL (wie FETCH, aber fragt vorher die HW, kann dauern)
  * TRIGGER (Wie POLL, aber die Antworten kommen als Events, return sofort)

Außer EVENT und ERROR (beides nur als Reply) gibts es jede Message als Request und als Reply.
Das Parsing einer Message ist eindeutig, so hat jeder reply mindestens ein '=', jede Mehrfachantwort endet mit '`#<anzahl messages>`', uswusf.
F&uuml;r das Parsing wird eine Regexp empfohlen, da die syntax nicht sonderlich parsingfreundlich ist.

Um auszuw&auml;hlen, auf welche Objekte eine Nachricht wirkt, werden folgende Argumente verwendet:

  - `*` wirkt auf alle devices
  - `device` wirkt auf das Device
  - `device:*` wirkt auf alle parameter des gegebenen devices
  - `device:param` wirkt auf den Parameter des Device
  - `device:param:*` wirkt auf alle properties des gegebenen parameters
  - `device:param:property` wirkt auf die property

Properties sind immer ReadOnly Softwarewerte. Somit haben WRITE, TRIGGER, (UN)SUBSCRIBE auf properties keinen sinn und sind mit einem Error zu beantworten.
(welcher? ProtokollError?=

Replies enthalten immer genau eine Antwort.
Der immer anzugebende 'Antwortwert' wird durch `=` von einer kopie des requestes abgetrennt.
F&uuml;r Multi-Antworten endet die Antwort in `#<number of replyitems>\n` statt in `\n`.
Hier ist kein '=' zus&auml;tzlich anzugeben. Nach dieser 'Er&ouml;ffnungsnachricht' kommen die angegebene Anzahl Antworten als Read-Replies.

Damit ergeben sich folgende Kombinationen (immer zuerst der Request, direkt drunter der Reply, direkt drunter die Beschreibung):
Danach die 'dringlichkeit des implementierens':
MANDATORY > RECOMMENDED > OPTIONAL

Werte sind entweder Zahlen (`1.23`) oder Strings (`"Ein String"` oder `Text`).
Solange eindeutigkeit besteht (kein '" ", ",", oder " im String) k&ouml;nnen die `"` weggelassen werden. Beispiel: unit=T


LIST
----

  * 'LIST *' oder 'LIST'
  * 'LIST *=mf,tc1,tc1,ts,...' oder 'LIST=mf,tc1,...'
  * ListDevices: returns ',' separated list of devicenames
  * MANDATORY

---------------

  * 'LIST `<devname>`'
  * 'LIST `<devname>`=status, target, value,...'
  * ListParameters: returns ',' separated list of parameternames for a device
  * MANDATORY

---------------

  * 'LIST `<devname>:<paramname>`'
  * 'LIST `<devname>:<paramname>`=timestamp, unit, description,...'
  * ListProperties: returns ',' separated list of propertynames for a parameter
  * MANDATORY


READ/WRITE
----------

  * 'READ `<devname>`'
  * 'READ `<devname>=<value>; [<qualname> '=' <qualvalue> ';']`'
  * ReadDevice: returns current device value + qualifiers
  * MANDATORY

---------

  * 'READ `<devname>:<paramname>`'
  * 'READ `<devname>:<paramname>=<value>; [<qualname> '=' <qualvalue> ';']`'
  * ReadParameter: returns current parameter value (+ qualifiers?)
  * MANDATORY

--------

  * 'READ `<devname>:<paramname>:<property>`'
  * 'READ `<devname>:<paramname>:<property>=<value>;`'
  * ReadProperty: returns curent value of property
  * RECOMMENDED

--------

  * 'WRITE `<devname>=<value>`'
  * 'WRITE `<devname>=<value>=<readbackvalue>; [<qualname> '=' <qualvalue> ';']`'
  * WriteDevice: sets new device-value and returns read-back target value + non-empty qualifiers! (at least the `;` must be present)
  * MANDATORY

--------

  * 'WRITE `<devname>:<paramname>=<value>`'
  * 'WRITE `<devname>:<paramname>=<value>=<readbackvalue>; [<qualname> '=' <qualvalue> ';']`'
  * WriteParameter: sets new parameter-value and returns read-back value + non-empty qualifiers! (at least the `;` must be present)
  * MANDATORY


COMMAND
-------

  * 'COMMAND `<device>:<command>'(' [<argument> ','] ')'`'
  * 'COMMAND `<device>:<command>'(' [<argument> ','] ')=' result`;'
  * ExecuteCommand: f&uuml;hrt command mit den gegebenen Arguments aus.
    result=(ein) R&uuml;ckgabewert, kann auch "OK" sein, falls kein R&uuml;ckgabewert definiert wurde.
  * MANDATORY

commands sind parameter deren name auf '()' endet.
(oder die argumenttypen in () enth&auml;lt?)

(UN)SUBSCRIBE
-------------

  * 'SUBSCRIBE `<device>`'
  * 'SUBSCRIBE `<device>=OK`;'
  * SubscribeDevice: subscribed auf den devicevalue (evtl auch auf den status?)
  * RECOMMENDED
  * possible extension: include a 'FETCH `<device>`' reply as Multi

--------

  * 'SUBSCRIBE `<device>`'
  * 'SUBSCRIBE `<device>=<list_of_subscribed_parameternames>`;'
  * SubscribeALLParameter: subscribed alle parameter eines device
  * RECOMMENDED
  * possible extension: include a 'FETCH `<device>:`' reply as Multi

--------

  * 'SUBSCRIBE `<device>:<param>`'
  * 'SUBSCRIBE `<device>:<param>=OK`;'
  * SubscribeParameter: subscribed auf den parameter
  * RECOMMENDED
  * possible extension: include a 'FETCH `<device>:<param>`' reply as Multi

--------

  * 'UNSUBSCRIBE `<device>`'
  * 'UNSUBSCRIBE `<device>=OK`;'
  * UNSubscribeDevice: unsubscribed auf den devicevalue
  * RECOMMENDED
  * possible extension: return list of remaining subscriptions as multi

--------

  * 'UNSUBSCRIBE `<device>:`'
  * 'UNSUBSCRIBE `<device>:=OK`;'
  * UNSubscribeALLParameter: unsubscribed alle parameter eines device
  * RECOMMENDED
  * possible extension: return list of remaining subscriptions as multi

--------

  * 'UNSUBSCRIBE `<device>:<param>`'
  * 'UNSUBSCRIBE `<device>:<param>=OK`;'
  * UNSubscribeParameter: unsubscribed auf den parameter
  * RECOMMENDED
  * possible extension: return list of remaining subscriptions as multi

Was ist zu tun bei einem unsubscribe auf einen nicht subscribten wert?
(doppeltes unsubscribe nach subscribe, etc...)

EVENT
-----

  * EVENT gibt es nicht als Request, da es nur als async reply auftaucht
  * '`#3\n`EVENT READ `mf=1.2\n`EVENT READ `mf:target=2.0\n`EVENT READ `mf:status="BUSY"\n`'
  * Event: sendet ein subscribed event, kann 0..N READ-replies beinhalten
  * RECOMMENDED

FETCH/POLL
----------

  * 'FETCH :' oder 'FETCH'
  * 'FETCH `:#2\nREAD mf=1.2\nREAD ts=3.4\n`' oder 'FETCH`#2\nREAD mf=1.2\nREAD ts=3.4\n`'
  * FetchDevices: reads and returns the values of all (interesting?) devices
  * OPTIONAL

--------

  * 'FETCH `<device>`'
  * 'FETCH mf#2\nREAD mf:value=1.2\nREAD mf:status="IDLE"\n`'
  * FetchDevice: reads and returns the (interesting?) parameters of a device
  * OPTIONAL

--------

  * 'FETCH `<device>:`'
  * 'FETCH `mf:#3\nREAD mf:value=1.2\nREAD mf:target=1.2\nREAD mf:status="IDLE"\n`'
  * FetchParameters: reads and returns the values of all parameters of a device
  * OPTIONAL

--------

  * 'FETCH `<device>:<parameter>`'
  * 'FETCH `mf:value#2\nREAD mf:value:unit="T"\nREAD mf:value:type=float\n`'
  * FetchParameter: reads and returns the properties of a single parameter
  * OPTIONAL

--------

  * 'FETCH `<device>:<parameter>:`'
  * 'FETCH `mf:value:#2\nREAD mf:value:unit="T"\nREAD mf:value:type=float\n`'
  * FetchProperties: reads and returns the values of all properties of a parameter
  * OPTIONAL

POLL wird wie FETCH kodiert, fragt aber die HW vor der Antwort, FECTH liefert zwischengespeicherte Werte.

TRIGGER
-------

  * 'TRIGGER :' oder 'TRIGGER'
  * 'TRIGGER :=OK' oder 'TRIGGER=OK'
  * TriggerDeviceReads: startet auslesen aller devices und &uuml;bertragen der (subscribed) values als events
  * OPTIONAL

--------

  * 'TRIGGER `<device>`'
  * 'TRIGGER `mf=OK`'
  * TriggerDeviceRead: startet auslesen eines Devices
  * OPTIONAL

--------

  * 'TRIGGER `<device>:`'
  * 'TRIGGER `mf:=OK`'
  * TriggerParameterReads: startet auslesen aller paremeter und &uuml;bertragen der subscribed parameter als events
  * OPTIONAL

--------

  * 'TRIGGER `<device>:<parameter>`'
  * 'TRIGGER `mf:value=OK`'
  * FetchProperties: reads and returns the values of all properties of a parameter
  * OPTIONAL

ERROR
-----

  * ERROR gibt es nicht als request, da es nur als reply auftaucht
  * 'ERROR `<errorclass> "<copy of request>" [<additional text>]`'
  * Error: zeigt einen Fehler an. folgende <errorclass> sind definiert:
    * NoSuchDevice
    * NoSuchParameter
    * NoSuchCommand
    * NoSuchProperty
    * CommandFailed
    * ReadOnly
    * BadValue
    * CommunicationFailed
    * IsBusy
    * IsError
    * ProtocolError
    * SyntaxError
  * MANDATORY


M&ouml;glich Erweiterung: f&uuml;r device/param/property kann statt eines einzelnamens auch eine ',' separierte Liste verwendet werden.
Außerdem k&ouml;nnte auch ein '*' f&uuml;r 'ALLE' stehen.
Die Antworten sind dann auf jeden Fall als Multi zu kodieren. Beispiel:

 > READ mf:target,value
 > > READ mf:target,value#2
 >
 > > READ mf:target=1.23
 >
 > > READ mf:value=0.73
 >

