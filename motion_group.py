from . import trio_socket
import trio


# hardware level: called by group
class XpsPositioner:
    max_accel: float = None
    max_velocity: float = None

    min_position: float = None
    max_position: float = None

    def __init__(self, name: str, stage_type: str, plug_number: str) -> None:
        self.name = name
        self.stage_type = stage_type
        self.plug_number = plug_number

    async def find_hardware_limits(self, sock: trio_socket.AsyncSocket) -> None:
        await self._find_max_vel_and_accel(sock)
        await self._find_travel_lims(sock)

    async def hardware_status_get(self, sock: trio_socket.AsyncSocket) -> str:
        # PositionerHardwareStatusGet :  Read positioner hardware status
        hardware_status_code = await sock.send_recv(f"PositionerHardwareStatusGet({self.name},int *)")
        # PositionerHardwareStatusStringGet :  Return the positioner hardware status string corresponding to the positioner error code
        return await sock.send_recv(f"PositionerHardwareStatusStringGet({hardware_status_code}, char *)")

    async def get_positioner_errors(self, sock: trio_socket.AsyncSocket) -> str:
        # PositionerErrorGet :  Read and clear positioner error code
        hardware_status_code =  await sock.send_recv(f"PositionerErrorGet({self.name},int *)")
        # PositionerErrorStringGet :  Return the positioner status string corresponding to the positioner error code
        return await sock.send_recv(f"PositionerErrorStringGet({hardware_status_code}, char *)")

##################

    async def _find_travel_lims(self, sock: trio_socket.AsyncSocket) -> None:
        try:
            (self.min_position, self.max_position) = await self._get_travel_lims(sock)
        except:
            print(f"could not set travel lims for {self.name}")

    # PositionerTravelLimitsGet :  Return maximum and minimum possible displacements of the positioner
    async def _get_travel_lims(self, sock: trio_socket.AsyncSocket) -> tuple:
        lo_lim, hi_lim = await sock.send_recv(
            f"PositionerUserTravelLimitsGet({self.name},double *,double *)")
        return float(lo_lim), float(hi_lim)

    async def _find_max_vel_and_accel(self, sock: trio_socket.AsyncSocket) -> None:
        try:
            self.max_velocity, self.max_accel = await self._get_positioner_max_vel_and_accel(sock)
        except:
            print("could not set max velo/accel for {self.name}")

    # PositionerMaximumVelocityAndAccelerationGet :  Return maximum velocity and acceleration of the positioner
    async def _get_positioner_max_vel_and_accel(self, sock: trio_socket.AsyncSocket) -> tuple:
        try:
            max_velocity, max_accel = await sock.send_recv(
                f"PositionerMaximumVelocityAndAccelerationGet({self.name},double *,double *)")
            return float(max_velocity), float(max_accel)
        except:
            print("could not set max velo/accel for {self.name}")


# callable by xps
class XpsMotionGroup():
    positioner: XpsPositioner = None
    type = "SingleAxes"

    def __init__(self, name: str) -> None:
        self.name = name

    async def add_positioner(self, name, stage_type: str,
                             plug_number: str, sock: trio_socket.AsyncSocket):
        self.positioner = XpsPositioner(name, stage_type, plug_number)
        await self.positioner.find_hardware_limits(sock)

    async def get_full_status(self, sock: trio_socket.AsyncSocket) -> str:
        out = []
        group_status = await self.get_status(sock)
        hardware_status = await self.get_positioner_status(sock)
        positioner_errors = await self.get_positioner_errors(sock)

        out.append(f"{self.name} ({self.type}), Status: {group_status}")
        out.append(f"   {self.positioner.name} {self.positioner.stage_type}")
        out.append(f"      Hardware Status: {hardware_status}")
        out.append(f"      Positioner Errors: {positioner_errors}")
        return "\n".join(out)

    async def get_positioner_status(self, sock: trio_socket.AsyncSocket):
        return await self.positioner.hardware_status_get(sock)

    # GroupStatusGet :  Return group status
    async def get_status(self, sock: trio_socket.AsyncSocket):
        return int(await sock.send_recv(f"GroupStatusGet({self.name},int *)"))
        # todo: some error handling based off looking for "ready" in "GroupStatusListGet(char *)"

    async def get_positioner_errors(self, sock: trio_socket.AsyncSocket):
        return await self.positioner.get_positioner_errors(sock)

    # GroupPositionCurrentGet :  Return current positions
    async def get_current_position(self, sock: trio_socket.AsyncSocket) -> float:
        position = await sock.send_recv(f"GroupPositionCurrentGet({self.name},double *)")
        return float(position)

    # GroupPositionTargetGet :  Return target positions
    async def get_target_position(self, sock: trio_socket.AsyncSocket):
        position = await sock.send_recv(f"GroupPositionTargetGet({self.name},double *)")
        return float(position)

    # GroupVelocityCurrentGet :  Return current velocities
    async def get_current_velocity(self, sock: trio_socket.AsyncSocket):
        velocity = await sock.send_recv(f"GroupVelocityCurrentGet({self.name},double *)")
        return float(velocity)

    # GroupMoveAbsolute :  Do an absolute move
    async def move_to(self, sock: trio_socket.AsyncSocket, target_position):
        #todo check target position: lock the stage
        self.check_position_within_limits(target_position)
        ret_str = await sock.send_recv(f"GroupMoveAbsolute({self.name},{target_position})")
        return ret_str

    # GroupMoveRelative :  Do a relative move
    async def move_by(self, sock: trio_socket.AsyncSocket, relative_movement):
        ret_str = await sock.send_recv(f"GroupMoveRelative({self.name},{relative_movement})")
        return ret_str

    def check_position_within_limits(self, position:float):
        assert (position < self.positioner.max_position), "target position beyond max"
        assert(position > self.positioner.min_position), "target position beyond min"

    # GroupInitialize :  Start the initialization
    async def initialise(self, sock: trio_socket.AsyncSocket):
        return await sock.send_recv(f"GroupInitialize({self.name})")

    # GroupHomeSearch :  Start home search sequence
    async def search_for_home(self, sock: trio_socket.AsyncSocket):
        return await sock.send_recv(f"GroupHomeSearch({self.name})")
