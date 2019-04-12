import sys, os
from . import ftp_wrappers
from collections import OrderedDict
import time
from socket import getfqdn


# todo exceptions are not handled
class XPSException(Exception):
    """XPS Controller Exception"""

    def __init__(self, msg, *args):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class XpsFactory:

    def build(self, sock):
        model, firmware_version = self.determine_xps_model(sock)
        if model == "C":
            xps = NewportXpsC(sock, firmware_version)
        elif model == "D":
            xps = NewportXpsD(sock, firmware_version)
        elif model == "Q":
            xps = NewportXpsQ(sock, firmware_version)

        return xps

    def determine_xps_model(self, sock):

        firmware_version = NewportXps.firmware_version_get(sock)

        if 'XPS-C' in firmware_version:
            model = "C"
        elif 'XPS-D' in firmware_version:
            # todo test on XPS-D
            model = "D"
            val = sock.send_recv('InstallerVersionGet(char *)')
            firmware_version = val
        elif 'XPS-Q' in firmware_version:
            model = "Q"
        else:
            raise XPSException(f"Unrecognised Model from firmware string '{firmware_version}'")

        return model, firmware_version


class NewportXps:
    groups = {}

    def __init__(self, sock, firmware_version, username='Administrator', password='Administrator'):

        self.host = sock.host
        self.username = username
        self.password = password
        self.firmware_version = firmware_version

        # todo : test when this is needed? not for 5001 access I think!
        # try:
        #     self._login(sock, username, password)
        # except:
        #     raise XPSException(f"Login failed for {username} at " +
        #                        f"{sock.host}:{sock.port_number}")

        self._setup_ftp_client()

        # todo : merge in the ftp functions
        self._setup_stage_and_group_info(sock)

    def status_report(self, sock):
        """return printable status report"""

        out = self._create_status_header(sock)

        out.append("# Groups and Stages")
        hstat = self._get_hardware_status()
        return out

        # perrs = self.get_positioner_errors()
        #
        # for groupname, status in self.get_group_status().items():
        #     this = self.groups[groupname]
        #     out.append("%s (%s), Status: %s" %
        #                (groupname, this['category'], status))
        #     for pos in this['positioners']:
        #         stagename = '%s.%s' % (groupname, pos)
        #         stage = self.stages[stagename]
        #         out.append("   %s (%s)"  % (stagename, stage['stagetype']))
        #         out.append("      Hardware Status: %s"  % (hstat[stagename]))
        #         out.append("      Positioner Errors: %s"  % (perrs[stagename]))
        # return "\n".join(out)

#########################################################

    def _get_hardware_status(self, sock):
        """
        get dictionary of hardware status for each stage
        """
        out = OrderedDict()
        for stage in self.stages.items():
            stat = stage.hardware_status_get(sock)
            print(f"hardware status = {stat}")
            stat = stage.hardware_status_string_get(sock, stat)
            print(f"hardware status string = {stat}")
        return out

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

#########################################################

    # ElapsedTimeGet :  Return elapsed time from controller power on
    def _calculate_boot_time(self, sock):
        uptime = sock.send_recv(f'ElapsedTimeGet(double *)')
        boot_time = time.time() - float(uptime)
        return boot_time

    def _create_status_header(self, sock):

        boot_time = self._calculate_boot_time(sock)

        out = ["# XPS host:         %s (%s)" % (self.host, getfqdn(self.host)),
               "# Firmware:         %s" % self.firmware_version,
               "# Current Time:     %s" % time.ctime(),
               "# Last Reboot:      %s" % time.ctime(boot_time),
               ]
        return out

    def _setup_ftp_client(self):
        raise NotImplemented

    def _ftp_args(self):
        return dict(host=self.host, username=self.username, password=self.password)

    def _setup_stage_and_group_info(self, sock):
        """read group info from system.ini
        this is part of the connection process
        """
        # get the lines via ftp connection
        config_dict = self.ftp.get_ini_info(self.ftphome)

        # get group names from groups section
        for group_type, groups_of_type in config_dict["GROUPS"].items():
            if "SingleAxis" not in group_type:
                raise Exception("bad group type: only single axis supported")
            single_ax_groups = [g for g in groups_of_type.split(", ")]

        # set up groups and positioners
        for group_name in single_ax_groups:
            self.groups[group_name] = XpsMotionGroup(group_name)

            positioner_name = config_dict[group_name]["PositionerInUse"]
            pos_hardware_name = f"{group_name}.{positioner_name}"
            pos_dict = config_dict[pos_hardware_name]

            stage_type = pos_dict["StageName"]
            plug_number = pos_dict["PlugNumber"]

            self.groups[group_name].add_positioner(pos_hardware_name, stage_type, plug_number, sock)

        return

    def _login(self, socket, username, password):
        return socket.send_recv(f"Login({username},{password})")

    # returns string of firmware version
    @staticmethod
    def firmware_version_get(socket):
        return socket.send_recv(f"FirmwareVersionGet(char *)")

class NewportXpsC(NewportXps):
    model = "C"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.FTPWrapper(**self._ftp_args())
        self.ftphome = '/Admin'

class NewportXpsD(NewportXps):
    model = "D"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.SFTPWrapper(**self._ftp_args())
        self.ftphome = ''

class NewportXpsQ(NewportXps):
    model = "Q"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.FTPWrapper(**self._ftp_args())
        self.ftphome = ''

# callable by xps
class XpsMotionGroup():
    positioners = None

    def __init__(self, name):
        self.name = name

    def add_positioner(self, name, stage_type, plug_number, sock):
        self.positioners = XpsPositioner(name, stage_type, plug_number, sock)

# hardware level: called by group
class XpsPositioner:
    max_accel = None
    max_velocity = None

    min_position = None
    max_position = None

    def __init__(self, name, stage_type, plug_number, sock):
        self.name = name
        self.stage_type = stage_type
        self.plug_number = plug_number

        self._find_max_vel_and_accel(sock)
        self._find_travel_lims(sock)

    # PositionerHardwareStatusGet :  Read positioner hardware status
    def hardware_status_get(self, sock):
        returnedString = sock.send_recv(f"PositionerHardwareStatusGet({self.name},int *)")
        return returnedString

    # PositionerHardwareStatusStringGet :  Return the positioner hardware status string corresponding to the positioner error code
    def hardware_status_string_get(self, sock, hardware_status):
        return sock.send_recv(f"PositionerHardwareStatusStringGet({hardware_status}, char *)")


    def _find_travel_lims(self, sock):
        try:
            (self.min_position, self.max_position) = self._get_travel_lims(sock)
        except:
            print(f"could not set travel lims for {self.name}")

    # PositionerTravelLimitsGet :  Return maximum and minimum possible displacements of the positioner
    def _get_travel_lims(self, sock):
        lo_lim, hi_lim = sock.send_recv(
            f"PositionerUserTravelLimitsGet({self.name},double *,double *)")
        print(f"pos travel lims = {lo_lim}, {hi_lim}")
        return float(lo_lim), float(hi_lim)

    def _find_max_vel_and_accel(self, sock):
        try:
            self.max_velocity, self.max_accel = self._get_positioner_max_vel_and_accel(sock)
        except:
            print("could not set max velo/accel for {self.name}")

    # PositionerMaximumVelocityAndAccelerationGet :  Return maximum velocity and acceleration of the positioner
    def _get_positioner_max_vel_and_accel(self, sock):
        max_velocity, max_accel = sock.send_recv(
            f"PositionerMaximumVelocityAndAccelerationGet({self.name},double *,double *)")

        print(f"positioner:{self.name}")
        print(f"pos max vel+acc =  {max_velocity}, {max_accel}")
        return float(max_velocity), float(max_accel)

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


