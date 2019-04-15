import sys, os
from . import ftp_wrappers
from collections import OrderedDict
import time
from socket import getfqdn
from . import motion_group


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
        for group in self.groups.values():
            out.append(group.get_full_status(sock))



        return "\n".join(out)


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
            self.groups[group_name] = motion_group.XpsMotionGroup(group_name)

            positioner_name = config_dict[group_name]["PositionerInUse"]
            pos_hardware_name = f"{group_name}.{positioner_name}"
            pos_dict = config_dict[pos_hardware_name]

            stage_type = pos_dict["StageName"]
            plug_number = pos_dict["PlugNumber"]

            self.groups[group_name].add_positioner(pos_hardware_name, stage_type, plug_number, sock)

        return

    # returns string of firmware version
    @staticmethod
    def firmware_version_get(socket):
        return socket.send_recv(f"FirmwareVersionGet(char *)")

#########################################################
    # ObjectsListGet :  Group name and positioner name
    def ObjectsListGet(self, sock):
        return sock.send_recv('ObjectsListGet(char *)')

    def _login(self, socket, username, password):
        return socket.send_recv(f"Login({username},{password})")



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

