from . import ftp_wrappers
import time
from socket import getfqdn
from . import motion_group
from . import trio_socket
import trio


# todo exceptions are not handled
class XPSException(Exception):
    """XPS Controller Exception"""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class XpsFactory:

    async def build(self, sock: trio_socket.AsyncSocket):
        model, firmware_version = await self.determine_xps_model(sock)

        host = sock.host
        if model == "C":
            xps = NewportXpsC(host, firmware_version)
        elif model == "D":
            xps = NewportXpsD(host, firmware_version)
        elif model == "Q":
            xps = NewportXpsQ(host, firmware_version)
        else:
            raise

        await xps.initialise_groups(sock)

        return xps

    @staticmethod
    async def determine_xps_model(sock):

        firmware_version = await NewportXps.firmware_version_get(sock)

        if 'XPS-C' in firmware_version:
            model = "C"
        elif 'XPS-D' in firmware_version:
            model = "D"
            val = await sock.send_recv('InstallerVersionGet(char *)')
            firmware_version = val
        elif 'XPS-Q' in firmware_version:
            model = "Q"
        else:
            raise XPSException(f"Unrecognised Model from firmware string '{firmware_version}'")

        return model, firmware_version


class NewportXps:
    groups = []
    ftp = None
    ftp_home = None

    def __init__(self, host, firmware_version, username='Administrator', password='Administrator'):

        self.host = host
        self.username = username
        self.password = password
        self.firmware_version = firmware_version

    async def initialise_groups(self, sock: trio_socket.AsyncSocket):
        self._setup_ftp_client()

        # todo : merge in the ftp functions
        await self._setup_stage_and_group_info(sock)

    async def status_report(self, sock: trio_socket.AsyncSocket):
        """return printable status report"""

        out = await self._create_status_header(sock)

        out.append("# Groups and Stages")
        for group in self.groups:
            out.append(await group.get_full_status(sock))

        return "\n".join(out)

#########################################################

    async def _create_status_header(self, sock: trio_socket.AsyncSocket):

        boot_time = await self._calculate_boot_time(sock)

        out = ["# XPS host:         %s (%s)" % (self.host, getfqdn(self.host)),
               "# Firmware:         %s" % self.firmware_version,
               "# Current Time:     %s" % time.ctime(),
               "# Last Reboot:      %s" % time.ctime(boot_time),
               ]
        return out

    # ElapsedTimeGet :  Return elapsed time from controller power on
    @staticmethod
    async def _calculate_boot_time(sock: trio_socket.AsyncSocket) -> float:
        uptime = await sock.send_recv(f'ElapsedTimeGet(double *)')
        boot_time = time.time() - float(uptime)
        return boot_time


    def _setup_ftp_client(self):
        raise NotImplemented

    def _ftp_args(self):
        return dict(host=self.host, username=self.username, password=self.password)

    async def _setup_stage_and_group_info(self, sock: trio_socket.AsyncSocket):
        """read group info from system.ini
        this is part of the connection process
        """
        # get the lines via ftp connection
        config_dict = self.ftp.get_ini_info(self.ftp_home)

        await trio.sleep(0)
        # get group names from groups section
        for group_type, groups_of_type in config_dict["GROUPS"].items():
            if "SingleAxis" not in group_type:
                raise Exception("bad group type: only single axis supported")
            else:
                single_ax_groups = [g for g in groups_of_type.split(", ")]
                for group_name in single_ax_groups:
                    self.groups.append(motion_group.XpsMotionGroup(group_name))

                    positioner_name = config_dict[group_name]["PositionerInUse"]
                    pos_hardware_name = f"{group_name}.{positioner_name}"
                    pos_dict = config_dict[pos_hardware_name]

                    stage_type = pos_dict["StageName"]
                    plug_number = pos_dict["PlugNumber"]

                    assert isinstance(plug_number, str)
                    await self.groups[-1].add_positioner(pos_hardware_name,
                                                                 stage_type,
                                                                 plug_number,
                                                                 sock)

        return

    # returns string of firmware version
    @staticmethod
    async def firmware_version_get(socket):
        return await socket.send_recv(f"FirmwareVersionGet(char *)")

#########################################################
    # functions to remove

    # ObjectsListGet :  Group name and positioner name
    @staticmethod
    async def get_object_list(sock):
        return sock.send_recv('ObjectsListGet(char *)')


class NewportXpsC(NewportXps):
    model = "C"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.FTPWrapper(**self._ftp_args())
        self.ftp_home = '/Admin'


class NewportXpsD(NewportXps):
    model = "D"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.SFTPWrapper(**self._ftp_args())
        self.ftp_home = ''


class NewportXpsQ(NewportXps):
    model = "Q"

    def _setup_ftp_client(self):
        self.ftp = ftp_wrappers.FTPWrapper(**self._ftp_args())
        self.ftp_home = ''
