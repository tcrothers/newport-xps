import trio
from contextlib import asynccontextmanager


class MyException(Exception):
    """XPS Controller Exception"""

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return str(self.msg)


class AsyncSocket:
    buffer_size = 2048
    _sock: trio.SocketStream

    def __init__(self, host: str, port: int = 5001):
        self.host = host
        self.port_number = port

    async def __aenter__(self):
        print("opening connection")
        self._sock = await trio.open_tcp_stream(self.host, self.port_number)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._sock.aclose()
        print("closing connection")

    # handles error, returns either a single string or tuple of strings
    async def send_recv(self, cmd):
        try:
            err, msg = await self._send_recv(cmd)
        # todo: implement and test error handling
        except trio.ClosedResourceError as my_err:
            err, msg = await self._cleanup(my_err)
            # because I closed the socket

        except trio.BrokenResourceError as my_err:
            # because socket closed from other side!
            raise my_err
            # another bad error
        # also applicable are MultiError and BusyResource

        if err != 0:
            raise MyException(msg)
        if len(msg) == 1:
            return msg[0]
        return msg

    async def _send_recv(self, msg: str):
        # send:
        command = msg
        await self._sock.send_all(command.encode())

        # receive:
        recieved_data = b''
        while recieved_data.find(b',EndOfAPI') == -1:
            recieved_data += await self._sock.receive_some(2048)
        reply = recieved_data.decode()

        parsed = reply.split(',')
        reply = (int(parsed[0]), parsed[1:-1])
        return reply

    async def _cleanup(self, my_err):
        print("noticed resource closed")
        # close the socket, re-connect, resend the command
        with trio.move_on_after(2) as cancel_scope:
            await self._sock.aclose()
            self._sock = await trio.open_tcp_stream(self.host, self.port_number)
        if cancel_scope.cancelled_caught:
            raise my_err
        err, msg = await self._send_recv(cmd)
        return err, msg

