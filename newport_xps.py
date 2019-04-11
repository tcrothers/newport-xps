import sys, os
from . import ftp_wrappers
from collections import OrderedDict
import time
from socket import getfqdn
# ideally can get rid of this:
from six.moves import StringIO
from six.moves.configparser import  ConfigParser



class XPSException(Exception):
    """XPS Controller Exception"""

    def __init__(self, msg, *args):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class NewportXps:
    groups = []
    stages = []
    firmware_version = None
    model = None

    def __init__(self, sock, username='Administrator', password='Administrator'):

        self.host = sock.host
        self.username = username
        self.password = password

        # todo : test when this is needed? not for 5001 access I think!
        try:
            self._login(sock, username, password)
        except:
            raise XPSException(f"Login failed for {username} at " +
                               f"{sock.host}:{sock.port_number}")


        self._determine_xps_model(sock)

        self._select_ftp_client()

        # todo : merge in the ftp functions
        self._read_systemini(sock)

    def status_report(self, sock):
        """return printable status report"""

        out = self._print_status_header(sock)

        out.append("# Groups and Stages")
        hstat = self.get_hardware_status()
        perrs = self.get_positioner_errors()

        for groupname, status in self.get_group_status().items():
            this = self.groups[groupname]
            out.append("%s (%s), Status: %s" %
                       (groupname, this['category'], status))
            for pos in this['positioners']:
                stagename = '%s.%s' % (groupname, pos)
                stage = self.stages[stagename]
                out.append("   %s (%s)"  % (stagename, stage['stagetype']))
                out.append("      Hardware Status: %s"  % (hstat[stagename]))
                out.append("      Positioner Errors: %s"  % (perrs[stagename]))
        return "\n".join(out)

    def _print_status_header(self, sock):

        boot_time = self._calculate_boot_time(sock)

        out = ["# XPS host:         %s (%s)" % (self.host, getfqdn(self.host)),
               "# Firmware:         %s" % self.firmware_version,
               "# Current Time:     %s" % time.ctime(),
               "# Last Reboot:      %s" % time.ctime(boot_time),
               ]
        return out

#########################################################

    def get_hardware_status(self, sock):
        """
        get dictionary of hardware status for each stage
        """
        out = OrderedDict()
        for stage in self.stages:
            if stage in ('', None): continue
            err, stat = self._xps.PositionerHardwareStatusGet(self._sid, stage)
            self.check_error(err, msg="Pos HardwareStatus '%s'" % (stage))

            err, val = self._xps.PositionerHardwareStatusStringGet(self._sid, stat)
            self.check_error(err, msg="Pos HardwareStatusString '%s'" % (stat))
            out[stage] = val
        return out

    # PositionerHardwareStatusGet :  Read positioner hardware status
    def PositionerHardwareStatusGet(self, socketId, PositionerName):
        command = 'PositionerHardwareStatusGet(' + PositionerName + ',int *)'
        error, returnedString = self.Send(socketId, command)
        if (error != 0):
            return [error, returnedString]

        i, j, retList = 0, 0, [error]
        while ((i + j) < len(returnedString) and returnedString[i + j] != ','):
            j += 1
        retList.append(eval(returnedString[i:i + j]))
        return retList


    def get_positioner_errors(self):
        """
        get dictionary of positioner errors for each stage
        """
        out = OrderedDict()
        for stage in self.stages:
            if stage in ('', None): continue
            err, stat = self._xps.PositionerErrorGet(self._sid, stage)
            self.check_error(err, msg="Pos Error '%s'" % (stage))

            err, val = self._xps.PositionerErrorStringGet(self._sid, stat)
            self.check_error(err, msg="Pos ErrorString '%s'" % (stat))

            if len(val) < 1:
                val = 'OK'
            out[stage] = val
        return out

    # ElapsedTimeGet :  Return elapsed time from controller power on
    def _calculate_boot_time(self, sock):
        uptime = sock.send_recv(f'ElapsedTimeGet(double *)')
        boot_time = time.time() - float(uptime)
        return boot_time

    def _determine_xps_model(self, sock):

        val = self._firmware_version_get(sock)
        print(val, sep="\n")
        self.firmware_version = val

        if 'XPS-C' in self.firmware_version:
            self.model = "C"
        elif 'XPS-D' in self.firmware_version:
            # todo test on XPS-D
            self.model = "D"
            val = sock.send_recv('InstallerVersionGet(char *)')
            self.firmware_version = val
        elif 'XPS-Q' in self.firmware_version:
            self.model = "Q"

    def _select_ftp_client(self):
        if self.model == "D":
            self.ftp = ftp_wrappers.SFTPWrapper(**self._ftp_args())
        else:
            self.ftp = ftp_wrappers.FTPWrapper(**self._ftp_args())

        if self.model == "C":
            self.ftphome = '/Admin'

    def _ftp_args(self):
        return dict(host=self.host, username=self.username, password=self.password)

    def _read_systemini(self, sock):
        """read group info from system.ini
        this is part of the connection process
        """
        self.ftp.connect(**self._ftp_args())
        self.ftp.cwd(os.path.join(self.ftphome, 'Config'))
        lines = self.ftp.getlines('system.ini')
        self.ftp.close()

        pvtgroups = []
        self.stages= OrderedDict()
        self.groups = OrderedDict()
        sconf = ConfigParser()
        sconf.readfp(StringIO('\n'.join(lines)))

        # read and populate lists of groups first
        for gtype, glist in sconf.items('GROUPS'): # ].items():
            if len(glist) > 0:
                for gname in glist.split(','):
                    gname = gname.strip()
                    self.groups[gname] = OrderedDict()
                    self.groups[gname]['category'] = gtype.strip()
                    self.groups[gname]['positioners'] = []
                    if gtype.lower().startswith('multiple'):
                        pvtgroups.append(gname)

        for section in sconf.sections():
            if section in ('DEFAULT', 'GENERAL', 'GROUPS'):
                continue
            items = sconf.options(section)
            if section in self.groups:  # this is a Group Section!
                poslist = sconf.get(section, 'positionerinuse')
                posnames = [a.strip() for a in poslist.split(',')]
                self.groups[section]['positioners'] = posnames
            elif 'plugnumber' in items: # this is a stage
                self.stages[section] = {'stagetype': sconf.get(section, 'stagename')}

        for sname in self.stages:
            velocity, accel = self._get_positioner_max_vel_and_accel(sock, sname)
            try:
                self.stages[sname]['max_velo']  = velocity
                self.stages[sname]['max_accel'] = accel
            except:
                print("could not set max velo/accel for %s" % sname)
            lo, hi = self._get_positioner_travel_lims(sock, sname)
            try:
                self.stages[sname]['low_limit']  = lo
                self.stages[sname]['high_limit'] = hi
            except:
                print("could not set limits for %s" % sname)

        return self.groups

    def _login(self, socket, username, password):
        return socket.send_recv(f"Login({username},{password})")

    # returns string of firmware version
    def _firmware_version_get(self, socket):
        return socket.send_recv(f"FirmwareVersionGet(char *)")

    # PositionerMaximumVelocityAndAccelerationGet :  Return maximum velocity and acceleration of the positioner
    def _get_positioner_max_vel_and_accel(self, sock, positioner_name):

        max_velocity, max_accel = sock.send_recv(
            f"PositionerMaximumVelocityAndAccelerationGet({positioner_name},double *,double *)")

        print(f"positioner:{positioner_name}")
        print(f"pos max vel+acc =  {max_velocity}, {max_accel}")
        return float(max_velocity), float(max_accel)

    # PositionerMaximumVelocityAndAccelerationGet :  Return maximum velocity and acceleration of the positioner
    def _get_positioner_travel_lims(self, sock, positioner_name):
        lo_lim, hi_lim = sock.send_recv(
            f"PositionerUserTravelLimitsGet({positioner_name},double *,double *)")

        print(f"pos travel lims = {lo_lim}, {hi_lim}")
        return float(lo_lim), float(hi_lim)


class XpsPositioner:

    # PositionerHardwareStatusGet :  Read positioner hardware status
    def PositionerHardwareStatusGet(self, socketId, PositionerName):
        command = 'PositionerHardwareStatusGet(' + PositionerName + ',int *)'
        error, returnedString = self.Send(socketId, command)
        if (error != 0):
            return [error, returnedString]

        i, j, retList = 0, 0, [error]
        while ((i + j) < len(returnedString) and returnedString[i + j] != ','):
            j += 1
        retList.append(eval(returnedString[i:i + j]))
        return retList
