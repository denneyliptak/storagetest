import socket
import datetime
import multiprocessing
import getopt
import sys

#modified version from: https://gist.github.com/micktwomey/606178

def handle(connection, address):
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("process-%r" % (address,))
    try:
        logger.debug("Connected %r at %r", connection, address)
        while True:
            data = connection.recv(1024)
            if data == "":
                logger.debug("Socket closed remotely")
                break
            logger.debug("Received data %r", data)
            #connection.sendall(data)
            #logger.debug("Sent data")
            print data
    except:
        logger.exception("Problem handling request")
    finally:
        logger.debug("Closing socket")
        connection.close()

class Server(object):
    def __init__(self, hostname, port):
        import logging
        self.logger = logging.getLogger("server")
        self.hostname = hostname
        self.port = port

    def start(self):
        self.logger.debug("listening")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.hostname, self.port))
        self.socket.listen(1)

        while True:
            conn, address = self.socket.accept()
            timestamp = 'Timestamp: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())
            self.logger.debug("Got connection at %s" % timestamp)
            process = multiprocessing.Process(target=handle, args=(conn, address))
            process.daemon = True
            process.start()
            self.logger.debug("Started process %r", process)

if __name__ == "__main__":

    # defaults
    servername = "localhost"
    port = "9000"
    options, remainder = getopt.getopt(sys.argv[1:], 'p:t:c:r:s:o', ['server=',
                                                                     'port=',
                                                                     ])
    for opt, arg in options:
        if opt in ('-s', '--server'):
            servername = arg
        elif opt in ('-o', '--port'):
            port = arg

    import logging
    logging.basicConfig(level=logging.INFO)
    server = Server(servername, int(port))
    try:
        logging.info("Listening on port %s" % port)
        server.start()
    except:
        logging.exception("Unexpected exception")
    finally:
        logging.info("Shutting down")
        for process in multiprocessing.active_children():
            logging.info("Shutting down process %r", process)
            process.terminate()
            process.join()
    logging.info("All done")