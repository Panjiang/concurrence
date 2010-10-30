import smtplib
from smtplib import *
from concurrence.io import Socket
from concurrence.io.buffered import Buffer, BufferedReader, BufferedWriter

# Use class concurrence.smtp.SMTP exactly like smtplib.SMTP

class SMTP(smtplib.SMTP):
    """ This is a subclass derived from SMTP that connects over a Concurrence socket """
    def _get_socket(self, host, port, timeout):
        new_socket = Socket.connect((host, port))
        self._reader = BufferedReader(new_socket, Buffer(1024))
        self._writer = BufferedWriter(new_socket, Buffer(1024))
        self.file = self._reader.file()
        return new_socket

    def send(self, str):
        if self.debuglevel > 0: print>>sys.stderr, 'send:', repr(str)
        if hasattr(self, 'sock') and self.sock:
            try:
                self._writer.write_bytes(str)
                self._writer.flush()
            except IOError:
                self.close()
                raise SMTPServerDisconnected('Server not connected')
        else:
            raise SMTPServerDisconnected('please run connect() first')

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self._reader = None
            self._writer = None
            self.file = None
