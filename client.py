import multiprocessing
import time
import logging
import errno
import os
import sys
import getopt
import uuid
import glob
import socket

from logging import handlers


class Datachunker(handlers.RotatingFileHandler):
    def doRollover(self):
        handlers.RotatingFileHandler.doRollover(self)
        message = "\n--*---Client pid %s: data file rollover---*--\n" % wData.pid
        sock.sendall(message)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def check_write_speed(e, path, chunkSizeMB, maxDataFileSizeMB, dataBlastDurationInSeconds):
    print "Checking write speed vs output file size for minimum required rollover count..."

    pTest = psutil.Process(os.getpid())
    pTest._starttime = time.time()
    pTest._before = pTest.io_counters()

    tmpfile = path + "/chunkSpeedTest" + str(uuid.uuid4())
    logger = logging.getLogger('chunkSpeed')
    logger.setLevel(logging.INFO)

    # Setting reasonable number of rolled data files, could base off of Inodes-(iUsed-someBuffer)
    MAX_ROLLED_DATAFILES = 10000

    chunk = "a" * chunkSizeMB * MEGA

    handler = handlers.RotatingFileHandler(tmpfile, 'wb', maxDataFileSizeMB*MEGA, MAX_ROLLED_DATAFILES)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Write a few chunks to get an idea of write speed.
    for x in range(0, 3, 1):
        logger.info(chunk)

    pTest._endtime = time.time()
    pTest._after = pTest.io_counters()
    writeBytesPerSec = (float(pTest._after.write_bytes) - float(pTest._before.write_bytes)) / \
                       float(pTest._endtime - pTest._starttime)
    writeMBPerSec = float(writeBytesPerSec/MEGA)

    numDataFiles = (writeMBPerSec * float(dataBlastDurationInSeconds)) / float(maxDataFileSizeMB)

    #In an ideal case, 2.00 would be sufficient. The 0.2 extra gives a 'fudge' factor to begin issuing the warning.
    if numDataFiles < 2.2:
        print "WARNING: Datafile rollover may happen fewer than 2 times. Increase runtime or decrease rollover size."

    #Cleanup temp files
    files = glob.glob(tmpfile + "*")
    for file in files:
        os.remove(file)


def write_data_to_disk(e, datadir, chunkSizeMB, maxDataFileSizeMB):
    filename = datadir + "/chunkydata" + str(uuid.uuid4())

    logger = logging.getLogger('chunky')
    logger.setLevel(logging.INFO)

    # Setting reasonable number of rolled data files, could base off of Inodes-(iUsed-someBuffer)
    MAX_ROLLED_DATAFILES = 10000

    chunk = "a" * chunkSizeMB * MEGA

    # Override RotatingFileHandler 'doRollover' so we can log when a rollover happens
    handler = Datachunker(filename, 'wb', maxDataFileSizeMB*MEGA, MAX_ROLLED_DATAFILES)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    while True:
        logger.info(chunk)


def monitor_data_to_disk(e, queue):
    wDataPID = queue.get()
    dataMonitor = psutil.Process(wDataPID)

    # grab first cpu_percent and discard/don't report (see documentation)
    dataMonitor.cpu_percent(interval=None)

    # grab initial io count, will use for calculating bytes written over a period of time:
    dataMonitor._before = dataMonitor.io_counters()
    dataMonitor._starttime = time.time()

    while True:
        time.sleep(10)
        dataMonitor._after = dataMonitor.io_counters()
        dataMonitor._endtime = time.time()
        writeBytesPerSec = (float(dataMonitor._after.write_bytes) - float(dataMonitor._before.write_bytes)) / float(
            dataMonitor._endtime - dataMonitor._starttime)
        # These messages should log to server only
        message = "\n--*---Client pid %s: Data test realtime status--*---\n" % wDataPID
        message += "\tCPU:\t%s%%\n" % dataMonitor.cpu_percent(interval=None)
        message += "\tMemory:\t%.2fMB\n" % float(float(dataMonitor.memory_full_info()[7])/MEGA)  # Unique Set Size
        message += "\tAverage Write bytes per sec: %.2f MB/s\n" % float(writeBytesPerSec/MEGA)
        sock.sendall(message)


def heartbeat(e):
    while True:
        time.sleep(5)
        # Send this to Server only
        #print '\n--*---heartbeat---*--\n'
        message = "\n--*---Client pid %s: heartbeat---*--\n" % PID
        sock.sendall(message)

if __name__ == '__main__':

    import imp

    try:
        imp.find_module('psutil')
        found = True
        import psutil
    except ImportError:
        found = False

    if not found:
        print "This client uses the psutil library which can be acquired throuhg pip. Exiting."
        sys.exit()

    # Constants/arguments:
    MEGA = 1000000

    options, remainder = getopt.getopt(sys.argv[1:], 'p:t:c:r:', ['path=',
                                                          'time=',
                                                          'chunk_size_mb=',
                                                          'rollover_size_mb',
                                                          ])
    for opt, arg in options:
        if opt in ('-p', '--path'):
            datadir = arg
        elif opt in ('-t', '--time'):
            dataBlastDurationInSeconds = int(arg)
        elif opt in ('-c', '--chunk_size_mb'):
            chunkSizeMB = int(arg)
        elif opt in ('-r', '--rollover_size_mb'):
            maxDataFileSizeMB = int(arg)

    print "path\t:", datadir

    #datadir = "/home/heavyd/tmpdata"
    #chunkSizeMB = 99
    #maxDataFileSizeMB = 100
    #dataBlastDurationInSeconds = 12

    e = multiprocessing.Event()
    queue = multiprocessing.Queue()

    # Make directory for data to be written to, if necessary:
    mkdir_p(datadir)

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Connect the socket to the port where the server is listening
    server_address = ('localhost', 6969)
    # print >>sys.stderr, 'connecting to %s port %s' % server_address
    sock.connect(server_address)

    # Check writespeed of a single chunk and warn if we don't expect more than 2 file rollovers
    wTest = multiprocessing.Process(name='writeTest',
                                    target=check_write_speed,
                                    args=(e,datadir,chunkSizeMB,maxDataFileSizeMB,dataBlastDurationInSeconds))
    wTest.start()
    wTest.join()

    wData = multiprocessing.Process(name='datablast',
                                    target=write_data_to_disk,
                                    args=(e,datadir,chunkSizeMB,maxDataFileSizeMB))

    wMonitor = multiprocessing.Process(name='datamonitor',
                                       target=monitor_data_to_disk,
                                       args=(e,queue,))

    wHeartbeat = multiprocessing.Process(name='heartbeat',
                                       target=heartbeat,
                                       args=(e,))

    wData.start()
    PID = wData.pid
    queue.put(PID)
    wMonitor.start()
    wHeartbeat.start()

    # Log start of data test
    message = '\n--*---Client pid %s: Beginning write test at %s for %ss' % (PID, datadir, str(dataBlastDurationInSeconds))
    print message
    sock.sendall(message)

    time.sleep(dataBlastDurationInSeconds)
    wData.terminate()
    wMonitor.terminate()
    wHeartbeat.terminate()

    # Log end of data test
    message = '\n--*---Client pid %s: Finished write test' % PID
    print message
    sock.sendall(message)

    sock.close()