from abc import ABC
import socket


class MyException(Exception):
    """XPS Controller Exception"""

    def __init__(self, msg, *args):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class AbstractSocket(ABC):

    _socket = None

    def __init__(self, ip_addr, port_number, timeout, blocking):

        self.host = ip_addr
        self.port_number = port_number

        #setup co-routine and prepare it to recieve command
        self._socket = self.socket_coroutine(ip_addr, port_number, timeout, blocking)
        self._socket.__next__()
        pass

    def socket_coroutine(self, a_socket):
        pass

    # handles error, returns either a single string or tuple of strings
    def send_recv(self, cmd):
        err, msg = self._socket.send(cmd)
        # todo this is a good place to place an error-check- needs implementing
        if err != 0:
            raise MyException(msg)
        if len(msg) == 1:
            return msg[0]
        return msg


class XpsSocket(AbstractSocket):

    buffer_size = 1024

    def __init__(self, host, port=5001, timeout=20.0, blocking=True):
        super(XpsSocket, self).__init__(host, port, timeout, blocking)

    def create_socket(self, host, port=5001, timeout=20.0, blocking=True):
        pass

    def socket_coroutine(self, ip_addr, port_number, timeout, blocking):
        try:
            new_socket = socket.socket()
            new_socket.connect((ip_addr, port_number))
            new_socket.settimeout(timeout)
            new_socket.setblocking(blocking)
            assert isinstance(new_socket, socket.socket)

            with new_socket as my_sock:
                msg = None
                while True:
                    # replaces __sendandrecieve
                    command = (yield msg)
                    my_sock.send(command.encode())

                    msg = my_sock.recv(self.buffer_size).decode()
                    while (msg.find(',EndOfAPI') == -1):
                        msg += my_sock.recv(self.buffer_size).decode()

                    if "," in msg:
                        msg = msg.split(",")
                        msg = [int(msg[0]), msg[1:-1]]
        except socket.timeout:
            yield [-2, '']
        except socket.error as err:  # (errNb, errString):
            print('Socket error : ', err.errno, err)
            yield [-2, '']


