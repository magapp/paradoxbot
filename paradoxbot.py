#!/usr/bin/env python
import sys, os, time, atexit
import argparse, ConfigParser
import serial, datetime, time
from signal import SIGTERM

import logging
import logging.handlers


def main(appname):
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version='%(prog)s https://github.com/magapp/'+appname)
    parser.add_argument('--debug', action='store_true', help='Log more')
    parser.add_argument('--config', action='store', help='Config file to use', metavar='FILENAME', default='paradoxbot.ini')
    parser.add_argument('--pid-file', action='store', help='Pid file to store pid in', metavar='FILENAME', default='/tmp/'+appname+'.pid')
    parser.add_argument('--start-daemon', action='store_true', help='Start daemon')
    parser.add_argument('--stop-daemon', action='store_true', help='Stop daemon')
    args = parser.parse_args()

    logger = setup_logging(appname, args.debug)
    defaults, cp = parse_config_file(args.config, parser.print_help)

    if args.stop_daemon:
        daemon = ParadoxbotDaemon(args.pid_file)
        daemon.stop(logger)
        print "Stopped daemon."
        sys.exit(0)

    print "Connecting to "+defaults["paradox_port"]+" at "+defaults["paradox_baud"]+" baud"
    ser = serial.Serial(port=defaults["paradox_port"], baudrate=defaults["paradox_baud"], parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0)
    paradox = Paradox(ser)
    if not paradox.check_if_available():
        print "Timeout talking trying to talk with Paradox, exit..."
        ser.close()
        sys.exit(1)
      
    print "Found Paradox."

    if args.start_daemon:
        print "Going daemon, see more infomration in syslog."
        daemon = ParadoxbotDaemon(args.pid_file)
        if not daemon.start(logger):
            print "Already running, restarting..."
            daemon.restart(logger)
            sys.exit(0)

    print "Testing went fine"
    ser.close()
    sys.exit(0)

def setup_logging(appname, debug):
    logger = logging.getLogger(appname)
    handler = logging.handlers.SysLogHandler(address = '/dev/log')
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARN)
    logger.addHandler(handler)
    return logger

def parse_config_file(configfile, print_help):
    cp = ConfigParser.ConfigParser()
    if not cp.read(configfile):
        print "Could not find config file "+configfile+"."
        print ""
        print_help()
        sys.exit(1)

    defaults = dict(cp.defaults())
    return defaults, cp

class Paradox():
    # Example event: G001N001A001
    event_group_name = {
       "000": "Zone '<label_zone>' is OK",
       "001": "Zone '<label_zone>' is Open",
       "002": "Zone '<label_zone>' is Tamper",
       "003": "Zone '<label_zone>' is Fire loop trouble",
       "004": "Non-reportable event <event_number> ",
       "005": "User code '<label_user>' entered",
       "006": "User/card '<label_user>' access on door",
       "007": "Bypass Programming access",
       "008": "TX Delay Zone Alarm",
       "009": "Arming with Master",
       "010": "Arming with User Code '<label_user>'",
       "011": "Arming with keyswitch '<label_user>'",
       "012": "Special arming",
       "013": "Disarm with Master",
       "014": "Disarm with User Code '<label_user>'",
       "015": "Disarm with Keyswitch '<label_user>'",
       "062": "Access granted for '<label_user>'",
       "063": "Access denied for '<label_user>'",
    }

    label_zones = dict()
    label_users = dict()

    def __init__(self, ser):
        self.ser = ser
        time.sleep(0.5)

    def check_if_available(self):
        for i in range(1,5):
            self.ser.write("RA001\r")
            time.sleep(0.5)
            status = self.ser.read(13)
            print str(status)
            if len(status) == 13 and "RA001" in status:
                return True
        return False

    def wait_command(self):
        data = ""
        while True:
            time.sleep(0.25)
            while self.ser.inWaiting() > 0:
                data += self.ser.read(1)
                if '\n' in data or '\r' in data:
                    break;
            if '\n' in data or '\r' in data:
                break;
    
        #logging.debug("Recieved line: "+data)
        return self._parse_data(data)
        
    
class Daemon:
        """
        A generic daemon class.
       
        Usage: subclass the Daemon class and override the run() method
        """
        def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
                self.stdin = stdin
                self.stdout = stdout
                self.stderr = stderr
                self.pidfile = pidfile
       
        def daemonize(self):
                """
                do the UNIX double-fork magic, see Stevens' "Advanced
                Programming in the UNIX Environment" for details (ISBN 0201563177)
                http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
                """
                try:
                        pid = os.fork()
                        if pid > 0:
                                # exit first parent
                                sys.exit(0)
                except OSError, e:
                        sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
                        sys.exit(1)
       
                # decouple from parent environment
                os.chdir("/")
                os.setsid()
                os.umask(0)
       
                # do second fork
                try:
                        pid = os.fork()
                        if pid > 0:
                                # exit from second parent
                                sys.exit(0)
                except OSError, e:
                        sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
                        sys.exit(1)
       
                # redirect standard file descriptors
                sys.stdout.flush()
                sys.stderr.flush()
                si = file(self.stdin, 'r')
                so = file(self.stdout, 'a+')
                se = file(self.stderr, 'a+', 0)
                os.dup2(si.fileno(), sys.stdin.fileno())
                os.dup2(so.fileno(), sys.stdout.fileno())
                os.dup2(se.fileno(), sys.stderr.fileno())
       
                # write pidfile
                atexit.register(self.delpid)
                pid = str(os.getpid())
                file(self.pidfile,'w+').write("%s\n" % pid)
       
        def delpid(self):
                os.remove(self.pidfile)
 
        def start(self, logger):
                """
                Start the daemon
                """
                # Check for a pidfile to see if the daemon already runs
                try:
                        pf = file(self.pidfile,'r')
                        pid = int(pf.read().strip())
                        pf.close()
                except IOError:
                        pid = None
       
                if pid:
                        message = "pidfile %s already exist. Daemon already running?\n"
                        sys.stderr.write(message % self.pidfile)
                        return False
               
                # Start the daemon
                self.daemonize()
                self.run(logger)
                return True 

        def stop(self, logger):
                """
                Stop the daemon
                """
                # Get the pid from the pidfile
                try:
                        pf = file(self.pidfile,'r')
                        pid = int(pf.read().strip())
                        pf.close()
                except IOError:
                        pid = None
       
                if not pid:
                        message = "pidfile %s does not exist. Daemon not running?\n"
                        sys.stderr.write(message % self.pidfile)
                        return # not an error in a restart
 
                logger.info("Stopping")

                # Try killing the daemon process       
                try:
                        while 1:
                                os.kill(pid, SIGTERM)
                                time.sleep(0.1)
                except OSError, err:
                        err = str(err)
                        if err.find("No such process") > 0:
                                if os.path.exists(self.pidfile):
                                        os.remove(self.pidfile)
                        else:
                                print str(err)
                                sys.exit(1)
 
        def restart(self, logger):
                """
                Restart the daemon
                """
                self.stop(logger)
                self.start(logger)
 
        def run(self):
                """
                You should override this method when you subclass Daemon. It will be called after the process has been
                daemonized by start() or restart().
                """

class ParadoxbotDaemon(Daemon):
    def run(self, logger):
        logger.debug('Starting 2')
        while True:
            #klogger.debug('this is debug')
            time.sleep(5)
 

if __name__ == "__main__":
    main(sys.argv[0].split(".")[0])

    def _parse_data(self, data):
        now = str(datetime.datetime.now())
        r = dict({"timestamp": now})
        r["event"] = data[0]
        r["raw"] = data.strip()
        r["description"] = "Unknown '%s'" % data.strip()

        if data[0] == "G":
            r["event"] = "G"
            r["event_group"] = data[1:4]
            r["event_number"] = int(data[5:8])
            try:
                r["area"] = int(data[9:12])
            except:
                r["area"] = 0
            try:
                r["description"] = self.event_group_name[r["event_group"]]
            except:
                r["description"] = "unknown %s/%d" % (r["event_group"], r["event_number"])

            r["description"] = r["description"].replace("<event_number>", str(r["event_number"]))

            try:
                r["description"] = r["description"].replace("<label_zone>", self.label_zones[str(r["event_number"]).zfill(3)])
            except:
                r["description"] = r["description"].replace("<label_zone>", str(r["event_number"]))

            try:
                r["description"] = r["description"].replace("<label_user>", self.label_users[str(r["event_number"]).zfill(3)])
            except:
                r["description"] = r["description"].replace("<label_user>", str(r["event_number"]))
            return r
    
        if data[0] == "Z" and data[1] == "L":
            r["event"] = "ZL"
            r["zone"] = str(data[2:5])
            r["name"] = data[5:].decode('iso-8859-1').encode('utf8').strip()
            print "Saving name '%s' for zone %s" % (r["name"], r["zone"])
            self.label_zones[r["zone"]] = r["name"]
            return r

        if data[0] == "U" and data[1] == "L":
            r["event"] = "UL"
            r["user"] = str(data[2:5])
            r["name"] = data[5:].decode('iso-8859-1').encode('utf8').strip()
            print "Saving name '%s' for user %s" % (r["name"], r["user"])
            self.label_users[r["user"]] = r["name"]
            return r

        return r

