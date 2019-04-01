=========
Todo List
=========

Open questions
==============

* Datatype for a mapping (like the calibration for the amagnet)
* How to set a Mapping or an enum (with all the name-value mappings) in the configfile?
* use toml vs. ini parser?
* error handling should be more consistent
* error-info stuff should be consistent
* dynamic device creation / modification (i.e. how to set the mapping of an enum during runtime?)
* propagation of units from main value to params
* switch params+cmds to 'accessibles'/attributes and keep in orderdDict?
  -> needs Datatype for a function
* datatype for funcion: is argin a list anyway, or just one (structured) argument?
  (so far we use a list and argout is a single datatype (which may be stuctured))
* polling: vendor specific or do we propose a common way to handle it?
  (playground uses a per-device pollinterval. params may be polled less often)
* interface classes !!! (maybe with feature mixins like WindowTimeout?)
* hardware access: unify? how?
* demo-hardware?
* If more than one connection exists: shall all events be relayed to all listeners?
* how about WRITE/COMMAND replies? Shall they go to all connected clients?
* structure of descriptive data needs to be specified
* same for JSON_stuff for Error Messages
* 'changed' may be 'readback'
* 'change' may be 'write'
* 'read' may be 'poll'
* the whole message may be json object (bigger, uglier to read)
* which events are broadcast or unicast?
* do we need a way to correlate a reply with a request?


Todos
=====

Structure
---------

 * stronger structure insides src

   * src/server for everything server related
   * src/client for everything client related (ProxyDevice!)
   * src/protocol for protocol specific things

     * need subtree for different implementations to play with

   * src/lib for helpers and other stuff

 * possibly a parallel src tree for cpp version


Client
------

 * maybe start with a python shell and some import magic
 * later a GUI may be a good idea
 * client: one connection for each device?
 * another connection for async data?


Server
------

 * rewrite MessageHandler to be agnostic of server
 * move encoding to interface
 * allow multiple interfaces per server
 * fix error handling an make it consistent

Device framework
----------------

 * supply properties for PARAMS to auto-generate async data units
 * self-polling support
 * generic devicethreads
 * proxydevice
 * make get_device uri-aware


Testsuite
---------

 * need a testsuite (pytest)
 * embedded tests inside the actual files grow difficult to maintain


Documentation
-------------

 * transfer build docu into wiki via automated jobfile




Transfer of blobs via json
--------------------------

 * use base64

