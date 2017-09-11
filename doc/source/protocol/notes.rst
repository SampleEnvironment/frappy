Notes
=====

No installation required or recommended
---------------------------------------

everything runs directly from the checkout.

you need:
 - python2.7.*
 - pip
 - linux OS (Mac may work as well)

install requirements with pip:
$ sudo pip install -r requirements.txt

to execute a program, prefix its name with bin/, e.g.:
$ bin/make_doc.py
$ bin/server.py start test

a testsuite is planned but nothing is there yet.

Structure
---------
 
* bin contains the executables (make_doc.py, server.py)
* doc is the root node of the docu (see index.md)
* etc contains the configurations for the server(s) and devices
* html contains the docu after make_doc.py was run
* log contains some (hopefully) log output from the servers
* pid contains pidfiles if a server is running
* src contains the python source

  * src/client: client specific stuff (proxy)
  * src/devices: devices to be used by the server (and exported via SECoP)
  * src/lib: helper stuff (startup, pidfiles, etc)
  * src/protocol: protocol specific stuff
  * src/errors.py: internal errors
  * src/server.py: device-managing part of the server (transport is in src/protocol/transport)
  * src/validators.py: validators used by the devices. may be moved to src/protocol


