# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO timeout
#TODO asyn dns resolve
from __future__ import with_statement

import time
import ssl
import logging
import httplib

from concurrence import Tasklet, Channel, Message, __version__, TimeoutError
from concurrence.timer import Timeout
from concurrence.io import Connector, BufferedStream
from concurrence.http import HTTPError, HTTPRequest, HTTPResponse
from socket import _socketobject
from concurrence.io.socket import Socket
from _ssl import SSLError

AGENT = 'Concurrence-Http-Client/' + __version__

CHUNK_SIZE = 1024 * 4

class HTTPConnection(object):
    """A HTTP 1.1 Client.

    Usage::

        #create an instance of this class and connect to a webserver using the connect method:
        cnn = HTTPConnection()
        cnn.connect(('www.google.com', 80))

        #create a GET request using the get method:
        request = cnn.get('/index.html')

        #finally perform the request to get a response:
        response = cnn.perform(request)

        #do something with the response:
        print response.body

    """

    log = logging.getLogger('HTTPConnection')

    def __init__(self):
        self.limit = None

    def connect(self, endpoint):
        """Connect to the webserver at *endpoint*. *endpoint* is a tuple (<host>, <port>)."""
        self._host = None
        if type(endpoint) == type(()):
            try:
                self._host = endpoint[0]
            except Exception:
                pass
        self._stream = BufferedStream(Connector.connect(endpoint), read_buffer_size = 1024 * 8, write_buffer_size = 1024 * 4)

    def set_limit(self, limit):
        self.limit = limit

    def receive(self):
        """Receive the next :class:`HTTPResponse` from the connection."""
        try:
            return self._receive()
        except TaskletExit:
            raise
        except EOFError:
            raise HTTPError("EOF while reading response")
        except HTTPError:
            raise
        except TimeoutError:
            raise
        except Exception:
            self.log.exception('')
            raise HTTPError("Exception while reading response")

    def _receive(self):

        response = HTTPResponse()

        with self._stream.get_reader() as reader:

            lines = reader.read_lines()

            #parse status line
            response.status = lines.next()

            #rest of response headers
            for line in lines:
                if not line: break
                key, value = line.split(': ')
                response.add_header(key, value)

            chunks = []

            if response.status_code != 204:
                #read data
                transfer_encoding = response.get_header('Transfer-Encoding', None)

                try:
                    content_length = int(response.get_header('Content-Length'))
                    if self.limit is not None and content_length > self.limit:
                        raise HTTPError("Response is too long")
                except Exception:
                    content_length = None

                #TODO better support large data, e.g. iterator instead of append all data to chunks

                if transfer_encoding == 'chunked':
                    while True:
                        chunk_line = reader.read_line()
                        chunk_size = int(chunk_line.split(';')[0], 16)
                        if chunk_size > 0:
                            data = reader.read_bytes(chunk_size)
                            reader.read_line() #chunk is always followed by a single empty line
                            chunks.append(data)
                        else:
                            reader.read_line() #chunk is always followed by a single empty line
                            break
                elif content_length is not None:
                    while content_length > 0:
                        n = min(CHUNK_SIZE, content_length)
                        data = reader.read_bytes(n)
                        chunks.append(data)
                        content_length -= len(data)
                else:
                    content_length = 0
                    while True:
                        try:
                            data = reader.read_bytes_available()
                        except EOFError:
                            break
                        chunks.append(data)
                        content_length += len(data)
                        if self.limit is not None and content_length > self.limit:
                            raise HTTPError("Response is too long")

            response.iter = chunks

            return response

    def get(self, path, host = None):
        """Returns a new :class:`HTTPRequest` with request.method = 'GET' and request.path = *path*.
        request.host will be set to the host used in :func:`connect`, or optionally you can specify a
        specific *host* just for this request.
        """
        request = HTTPRequest()
        request.method = 'GET'
        request.path = path
        request.host = host or self._host
        return request

    def post(self, path, body = None, host = None):
        """Returns a new :class:`HTTPRequest` with request.method = 'POST' and request.path = *path*.
        request.host will be set to the host used in :func:`connect`, or optionally you can specify a
        specific *host* just for this request.
        *body* is an optional string containing the data to post to the server.
        """
        request = HTTPRequest()
        request.method = 'POST'
        request.path = path
        request.host = host or self._host
        if body is not None:
            request.body = body
        return request

    def perform(self, request):
        """Sends the *request* and waits for and returns the :class:`HTTPResult`."""
        self.send(request)
        return self.receive()

    def send(self, request):
        """Sends the *request* on this connection."""
        if request.method is None:
            assert False, "request method must be set"
        if request.path is None:
            assert False, "request path must be set"
        if request.host is None:
            assert False, "request host must be set"

        with self._stream.get_writer() as writer:
            writer.clear()
            writer.write_bytes("%s %s HTTP/1.1\r\n" % (request.method, request.path))
            writer.write_bytes("Host: %s\r\n" % request.host)
            for header_name, header_value in request.headers:
                writer.write_bytes("%s: %s\r\n" % (header_name, header_value))
            writer.write_bytes("\r\n")
            if request.body is not None:
                writer.write_bytes(request.body)
            writer.flush()

    def close(self):
        """Close this connection."""
        self._stream.close()


HTTPS_CONNECTION_TIMEOUT = 15
sleep_time_dict = {1:0.1, 2:0.2, 3:0.7, 4:2.0}

class HTTPSConnection(httplib.HTTPSConnection):
    def connect(self, timeout=HTTPS_CONNECTION_TIMEOUT):
        "Connect to a host on a given (SSL) port."
        sock = Socket.connect((self.host, self.port), timeout=timeout)
        sock.socket.setblocking(1)
        _sock = _socketobject(_sock=sock.socket)
        
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
        self.sock = ssl.wrap_socket(_sock, self.key_file, self.cert_file)
        self.sock.setblocking(0)

def try_getresponse(cnn, times=1, sleep_time_dict=sleep_time_dict):
    """
    async https request need read response multiple times until timeout.
    """
    # must sleep, or throw exception:
    # _ssl.c:1354: The operation did not complete
    try:
        response = cnn.getresponse()
    except SSLError:
        sleep_time = sleep_time_dict.get(times, None)
        if sleep_time is None:
            assert False, 'request timeout'
        Tasklet.sleep(sleep_time)
        response = try_getresponse(cnn, times=times + 1)
    except:
        raise
    return response