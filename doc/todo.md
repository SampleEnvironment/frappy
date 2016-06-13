# TODO List #

## Structure ##

 * stronger structure insides src
   * src/server for everything server related
   * src/client for everything client related (ProxyDevice!)
   * src/protocol for protocol specific things
   * src/lib for helpers and other stuff
 * possibly a parallel src tree for cpp version


## A Client ##

 * maybe start with a python shell and some import magic
 * later a GUI may be a good idea
 * client: one connection for each device?
 * another connection for async data?


## A Server ##

 * evaluate config.ini
 * handle cmdline args (specify different server.ini)
 * support Async data units
 * support feature publishing and selection
 * rewrite MessageHadler to be agnostic of server


## Testsuite ##

 * embedded tests inside the actual files grow difficult to maintain
 * needed ?

 
