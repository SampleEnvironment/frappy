Heartbeat
=========
* ping gets an 'intended looptime' argument (as number in seconds or null to disable)
* server replys as usual
* if the server received no new message within twice the indended looptime, it may close the connection.
* if the client receives no pong within 3s it may close the connection
* later discussions showed, that the ping/pong should stay untouched and the keepalive time should be (de-)activated by a special message instead. Also the 'connection specific settings' from earlier drafts may be resurrected for this....

