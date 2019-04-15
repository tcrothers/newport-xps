

# callable by xps
class XpsMotionGroup():
    positioner = None
    type = "SingleAxes"

    def __init__(self, name):
        self.name = name

    def add_positioner(self, name, stage_type, plug_number, sock):
        self.positioner = XpsPositioner(name, stage_type, plug_number, sock)

    def get_full_status(self, sock):
        out = []

        group_status = self.get_status(sock)
        hardware_status = self.get_positioner_status(sock)
        positioner_errors = self.get_positioner_errors(sock)

        out.append(f"{self.name} ({self.type}), Status: {group_status}")
        out.append(f"   {self.positioner.name} {self.positioner.stage_type}")
        out.append(f"      Hardware Status: {hardware_status}")
        out.append(f"      Positioner Errors: {positioner_errors}")
        return "\n".join(out)

    def get_positioner_status(self, sock):
        return self.positioner.hardware_status_get(sock)

    # GroupStatusGet :  Return group status
    def get_status(self, sock):
        return int(sock.send_recv(f"GroupStatusGet({self.name},int *)"))
        # todo: test this return type

    def get_positioner_errors(self, sock):
        return self.positioner.get_positioner_errors(sock)

    # GroupPositionCurrentGet :  Return current positions
    def get_current_position(self, sock):
        position = sock.send_recv(f"GroupPositionCurrentGet({self.name},double *)")
        return float(position)

    # GroupPositionTargetGet :  Return target positions
    def get_target_position(self, sock):
        position = sock.send_recv(f"GroupPositionTargetGet({self.name},double *)")
        return float(position)

    # GroupVelocityCurrentGet :  Return current velocities
    def get_current_velocity(self, sock):
        velocity = sock.send_recv(f"GroupVelocityCurrentGet({self.name},double *)")
        return float(velocity)

    # GroupMoveAbsolute :  Do an absolute move
    def move_to(self, sock, target_position):
        #todo check target position
        ret_str = sock.send_recv(f"GroupMoveAbsolute({self.name},{target_position})")
        return ret_str

    # GroupMoveRelative :  Do a relative move
    def move_by(self, sock, relative_movement):
        ret_str = sock.send_recv(f"GroupMoveRelative({self.name},{relative_movement})")
        return ret_str

    # GroupInitialize :  Start the initialization
    def initialise(self, sock):
        return sock.send_recv(f"GroupInitialize({self.name})")

    # GroupHomeSearch :  Start home search sequence
    def search_for_home(self, sock):
        return sock.send_recv(f"GroupHomeSearch({self.name})")

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

    def hardware_status_get(self, sock):
        # PositionerHardwareStatusGet :  Read positioner hardware status
        hardware_status_code = sock.send_recv(f"PositionerHardwareStatusGet({self.name},int *)")
        # PositionerHardwareStatusStringGet :  Return the positioner hardware status string corresponding to the positioner error code
        return sock.send_recv(f"PositionerHardwareStatusStringGet({hardware_status_code}, char *)")

    def get_positioner_errors(self, sock):
        # PositionerErrorGet :  Read and clear positioner error code
        hardware_status_code =  sock.send_recv(f"PositionerErrorGet({self.name},int *)")
        # PositionerErrorStringGet :  Return the positioner status string corresponding to the positioner error code
        return sock.send_recv(f"PositionerErrorStringGet({hardware_status_code}, char *)")

##################

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
