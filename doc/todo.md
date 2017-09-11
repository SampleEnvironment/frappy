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

 * rewrite MessageHandler to be agnostic of server
 * move encoding to interface
 * allow multiple interfaces per server
 * fix error handling an make it consistent

## Device framework ##

 * supply properties for PARAMS to auto-generate async data units
 * self-polling support
 * generic devicethreads
 * proxydevice
 * make get_device uri-aware


## Testsuite ##

 * embedded tests inside the actual files grow difficult to maintain
=> need a testsuite (pytest)


## docu ##

 * mabe use sphinx to generate docu: a pdf can then be auto-generated....
 * transfer build docu into wiki via automated jobfile


 

## transfer of blobs via json ##

 * use base64

