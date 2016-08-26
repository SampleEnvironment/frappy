import asyncore
import socket

class LineHandler(asyncore.dispatcher_with_send):

    def __init__(self, sock):
        self.buffer = ""
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.crlf = 0

    def handle_read(self):
        data = self.recv(8192)
        if data:
            parts = data.split("\n")
            if len(parts) == 1:
                self.buffer += data
            else:
                self.handle_line(self.buffer + parts[0])
                for part in parts[1:-1]:
                    if part[-1] == "\r":
                        self.crlf = True
                        part = part[:-1]
                    else:
                        self.crlf = False
                    self.handle_line(part)
                self.buffer = parts[-1]

    def send_line(self, line):
        self.send(line + ("\r\n" if self.crlf else "\n"))

    def handle_line(self, line):
        '''
        test: simple echo handler
        '''
        self.send_line("> " + line)

class LineServer(asyncore.dispatcher):

    def __init__(self, host, port, lineHandlerClass):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)
        self.lineHandlerClass = lineHandlerClass

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            print "Incoming connection from %s" % repr(addr)
            handler = self.lineHandlerClass(sock)

    def loop(self):
        asyncore.loop()

if __name__ == "__main__":
    server = LineServer("localhost", 9999, LineHandler)
    server.loop()
