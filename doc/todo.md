# TODO List #

## Structure ##

 * stronger structure insides src
   * src/server for everything server related
   * src/client for everything client related (ProxyDevice!)
   * src/protocol for protocol specific things
     * need subtree for different implementations to play with
   * src/lib for helpers and other stuff
 * possibly a parallel src tree for cpp version


## A Client ##

 * maybe start with a python shell and some import magic
 * later a GUI may be a good idea
 * client: one connection for each device?
 * another connection for async data?


## A Server ##

 * get daemonizing working
 * handle -d (nodaemon) and -D (default, daemonize) cmd line args
 * support Async data units
 * support feature publishing and selection
 * rewrite MessageHandler to be agnostic of server


## Device framework ##

 * unify PARAMS and CONFIG (if no default value is given, 
it needs to be specified in cfgfile, otherwise its optional)
 * supply properties for PARAMS to auto-generate async data units


## Testsuite ##

 * embedded tests inside the actual files grow difficult to maintain
=> need a testsuite (nose+pylint?)


## docu ##

 * mabe use sphinx to generate docu: a pdf can then be auto-generated....
 * transfer build docu into wiki via automated jobfile
Problem: wiki does not understand .md or .html


 
