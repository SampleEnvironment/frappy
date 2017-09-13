Commands
========

The "done" message should be returned quickly, the time scale should
be in the order of the time needed for communications. Actions which have
to wait for physical changes, can be triggered with a command. 
The information about the success of such an action has to be transferred
via parameters, namely the status parameter.

A command has at least the following properties:

:description:
  tell what this command does

:arguments:
  a list of datatypes for the command arguments (may be empty)

:resulttype:
  the type of the result (may be null)
  

  
