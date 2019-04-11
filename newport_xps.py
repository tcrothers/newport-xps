import sys, os
from . import ftp_wrappers
from collections import OrderedDict
import time
from socket import getfqdn



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

    def __init__(self, socket, username='Administrator', password='Administrator'):

        self.host = socket.host
        self.username = username
        self.password = password

        # todo : test when this is needed? not for 5001 access I think!
        try:
            self._login(socket, username, password)
        except:
            raise XPSException(f"Login failed for {username} at " +
                               f"{socket.host}:{socket.port_number}")


        self._determine_xps_model(socket)

        self._select_ftp_client()

        # todo : merge in the ftp functions
        # self._read_systemini()

    def status_report(self, socket):
        """return printable status report"""

        out = self.print_status_header()

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

    def print_status_header(self, sock):

        boot_time = self.calculate_boot_time(sock)

        out = ["# XPS host:         %s (%s)" % (self.host, getfqdn(self.host)),
               "# Firmware:         %s" % self.firmware_version,
               "# Current Time:     %s" % time.ctime(),
               "# Last Reboot:      %s" % time.ctime(boot_time),
               ]
        return out

#########################################################

    # ElapsedTimeGet :  Return elapsed time from controller power on
    def calculate_boot_time(self, socket):
        [err, uptime] = socket.send_recv(f'ElapsedTimeGet(double *)')
        self._check_error(err, msg="calculate_boot_time")
        boot_time = time.time() - float(uptime)
        return boot_time

    def _check_error(self, err, msg='', with_raise=True):
        if err is not 0:
            err = "%d" % err
            # desc = self._xps.errorcodes.get(err, 'unknown error')
            print(f"XPSError [Error {err}]: in {msg}")
            if with_raise:
                raise XPSException(f"XPSError [Error {err}]: in {msg}")

    def _determine_xps_model(self, socket):

        err, val = self._firmware_version_get(socket)
        print(err, val, sep="\n")
        self.firmware_version = val

        if 'XPS-C' in self.firmware_version:
            self.model = "C"
        elif 'XPS-D' in self.firmware_version:
            # todo test on XPS-D
            self.model = "D"
            err, val = socket.send_recv('InstallerVersionGet(char *)')
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

    def _read_systemini(self):
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

        if len(pvtgroups) == 1:
            self.set_trajectory_group(pvtgroups[0])

        for sname in self.stages:
            ret = self._xps.PositionerMaximumVelocityAndAccelerationGet(self._sid, sname)
            try:
                self.stages[sname]['max_velo']  = ret[1]
                self.stages[sname]['max_accel'] = ret[2]/3.0
            except:
                print("could not set max velo/accel for %s" % sname)
            ret = self._xps.PositionerUserTravelLimitsGet(self._sid, sname)
            try:
                self.stages[sname]['low_limit']  = ret[1]
                self.stages[sname]['high_limit'] = ret[2]
            except:
                print("could not set limits for %s" % sname)

        return self.groups

    def _login(self, socket, username, password):
        return socket.send_recv(f"Login({username},{password})")

    def _firmware_version_get(self, socket):
        return socket.send_recv(f"FirmwareVersionGet(char *)")
