#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Magnus Appelquist 2014-06-02 Initial
#
import ConfigParser, sys, os
import serial, datetime, time

def main():

    cp = ConfigParser.ConfigParser()
    if not cp.read('paradoxbot.ini'):
        print "Could not find config file 'paradoxbot.ini'"
        sys.exit(1)

    defaults = dict(cp.defaults())

    ser = serial.Serial(port=defaults["paradox_port"], baudrate=defaults["paradox_baud"], parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0)
    print "connected to: " + ser.portstr

    p = Paradox(ser)

    while True:
        data = p.wait_command()
        if data: 
            print "%s: %s (%s)" % (data["timestamp"], data["description"], data["raw"])
            #print "debug: %s" % str(data)
            for cmd in parse_event(cp, data["raw"]):
                #print cmd
                os.system(cmd+" >/dev/null 2>&1")
                #os.system(cmd)

    ser.close()


def parse_event(cp, event):
    cmds = list()
    for section in cp.sections():
        if cp.has_option(section, "events") and cp.has_option(section, "cmd"):
            #print "DEBUG: '%s' != '%s'" % (event ,str(cp.get(section, "events").split(",")))
            if event in [s.strip() for s in cp.get(section, "events").split(",")]:
                print "Event '%s'" % section
                cmds.append(render(dict(cp.defaults()), cp.get(section, "cmd")).replace('"',''))
    return cmds

def render(defaults, string):
    s = string
    for key, val in defaults.items():
        s = s.replace("$"+key, val.replace('"',''))
    return s

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

        if not self.check_if_available():
            print "No Paradox Alarm found. Try again."
            return

        # Probe all zone labels:
        print "Reading all zone labels..."
        #self.label_zones["000"] = "Uknown (0)"
        #self.label_users["000"] = "Uknown (0)"
        #for i in range(1,192):
        for i in range(1,40):
            if i%10 == 0: print "Found %d zones..." % i
            zone = str(i).zfill(3)
            ser.write("ZL%s\r" % zone)
            time.sleep(0.1)
            self.wait_command()

        # Probe all user labels:
        print "Reading all user labels..."
        #for i in range(1,999):
        for i in range(1,20):
            if i%10 == 0: print "Found %d users..." % i
            zone = str(i).zfill(3)
            ser.write("UL%s\r" % zone)
            time.sleep(0.1)
            self.wait_command()

    def check_if_available(self):
        for i in range(1,5):
            self.ser.write("RA001\r")
            time.sleep(0.5)
            status = self.ser.read(13)
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

if __name__ == "__main__":
    main()

