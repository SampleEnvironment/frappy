Structure of the descriptive json
=================================

* json = {"modules": &lt;list_of_modules&gt;, "properties": &lt;list_of_sec-node_properties&gt;, ...}
* module = {"name": &lt;name_of_module&gt;, "parameters": &lt;list_of_parameters&gt;, "commands": &lt;list_of_commands&gt;, "properties": &lt;list_of_module_properties&gt;}
* parameter = {"name": ..., "properties": &lt;list_of_properties&gt;}
* command = {"name": ..., "properties": &lt;list_of_properties&gt;}
* property = {"name":&lt;name&gt;, "datatype": &lt;datatype&gt;, "value": &lt;value&gt;}

note: property may also be [&lt;name&gt;,&lt;datatype&gt;,&lt;value&gt;]

