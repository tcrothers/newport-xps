#!/usr/bin/env python

from __future__ import print_function
import os
import ftplib
import six

# it appears ftp really wants this encoding:
FTP_ENCODING = 'latin-1'

def bytes2str(s):
    return str(s)


if six.PY3:
    from io import BytesIO as bytesio

    def bytes2str(s):
        'byte to string conversion'
        if isinstance(s, str):
            return s
        elif isinstance(s, bytes):
            return str(s, FTP_ENCODING)
        else:
            return str(s)


HAS_PYSFTP = False
try:
    import pysftp
    HAS_PYSFTP = True
except ImportError:
    pass

class FTPBaseWrapper(object):
    """base clase for ftp interactions for Newport XPS
    needs to be overwritten -- use SFTPWrapper or FTPWrapper"""
    def __init__(self, host=None, username='Administrator',
                 password='Administrator'):
        self.host = host
        self.username = username
        self.password = password
        self._conn = None

    def close(self):
        if self._conn is not None:
            self._conn.close()
        self._conn = None

    def cwd(self, remotedir):
        self._conn.cwd(remotedir)

    def connect(self, host=None, username=None, password=None):
        raise NotImplemented

    def save(self, remotefile, localfile):
        "save remote file to local file"
        raise NotImplemented

    def getlines(self, remotefile):
        "read text of remote file"
        raise NotImplemented

    def put(self, text, remotefile):
        "put text to remote file"
        raise NotImplemented


class SFTPWrapper(FTPBaseWrapper):
    """wrap ftp interactions for Newport XPS models D"""
    def __init__(self, host=None, username='Administrator',
                 password='Administrator'):
        FTPBaseWrapper.__init__(self, host=host,
                                username=username, password=password)

    def connect(self, host=None, username=None, password=None):
        if host is not None:
            self.host = host
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        if not HAS_PYSFTP:
            raise ValueError("pysftp not installed.")

        self._conn = pysftp.Connection(self.host,
                                       username=self.username,
                                       password=self.username)

    def save(self, remotefile, localfile):
        "save remote file to local file"
        self._conn.get(remotefile, remotefile)

    def getlines(self, remotefile):
        "read text of remote file"
        tmp = utils.bytesio()
        self._conn.getfo(remotefile, tmp)
        tmp.seek(0)
        text = utils.bytes2str(tmp.read())
        return text.split('\n')

    def put(self, text, remotefile):
        txtfile = utils.bytesio(six.b(text))
        self._conn.putfo(txtfile, remotefile)


class FTPWrapper(FTPBaseWrapper):
    """wrap ftp interactions for Newport XPS models C and Q"""
    def __init__(self, host=None, username='Administrator',
                 password='Administrator'):
        FTPBaseWrapper.__init__(self, host=host,
                                username=username, password=password)

    def connect(self, host=None, username=None, password=None):
        if host is not None:
            self.host = host
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        self._conn = ftplib.FTP()
        self._conn.connect(self.host)
        self._conn.login(self.username, self.password)

    def save(self, remotefile, localfile):
        "save remote file to local file"
        output = []
        x = self._conn.retrbinary('RETR %s' % remotefile, output.append)
        open_opts = {}
        if six.PY3:
            open_opts['encoding'] = utils.FTP_ENCODING
        with open(localfile, 'w', **open_opts) as fout:
            fout.write(''.join([utils.bytes2str(s) for s in output]))

    def getlines(self, remotefile):
        "read text of remote file"
        output = []
        self._conn.retrbinary('RETR %s' % remotefile, output.append)
        text = ''.join([utils.bytes2str(line) for line in output])
        return text.split('\n')

    def put(self, text, remotefile):
        txtfile = utils.bytesio(six.b(text))
        # print(" Put ", text, txtfile)
        self._conn.storbinary('STOR %s' % remotefile, txtfile)
