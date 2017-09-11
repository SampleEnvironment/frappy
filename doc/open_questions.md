
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

