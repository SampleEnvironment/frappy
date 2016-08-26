import fileinput

class LineHandler():

    def __init__(self, *args, **kwargs):
        pass

    def send_line(self, line):
        print " ", line

    def handle_line(self, line):
        '''
        test: simple echo handler
        '''
        self.send_line("> " + line)

class LineServer():

    def __init__(self, isfile, lineHandlerClass):
        self.lineHandlerClass = lineHandlerClass
        self.isfile = isfile

    def loop(self):
        handler = self.lineHandlerClass()
        while True:
            try:
                if self.isfile:
                    line = raw_input("")
                    print "> "+line
                else:
                    line = raw_input("> ")
            except EOFError:
                return
            handler.handle_line(line)

if __name__ == "__main__":
    server = LineServer("localhost", 9999, LineHandler)
    server.loop()
