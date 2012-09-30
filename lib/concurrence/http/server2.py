# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO write timeout

from __future__ import with_statement

import logging
import urlparse
import httplib
import traceback
import rfc822

from concurrence import Tasklet, Message, Channel, TimeoutError, __version__
from concurrence.io import Socket, Buffer, BufferedStream
from concurrence.containers import ReorderQueue
from concurrence.timer import Timeout
from concurrence.http import HTTPError, HTTPParser

SERVER_ID = "Concurrence-Http/%s" % __version__

class WSGIErrorStream(object):
    def write(self, s):
        logging.error(s)

    def writelines(self, s):
        assert False, 'TODO'

    def flush(self):
        assert False, 'TODO'

class WSGIRequest(object):
    log = logging.getLogger('WSGIRequest')

    def __init__(self, environ):
        self.environ = environ

        self.environ['SCRIPT_NAME'] = '' #TODO

        #add wsgi stuff
        self.environ['wsgi.url_scheme'] = 'http'
        self.environ['wsgi.multiprocess'] = False
        self.environ['wsgi.multithread'] = True
        self.environ['wsgi.run_once'] = False
        self.environ['wsgi.version'] = (1, 0)

        #wsgi complience
        if 'HTTP_CONTENT_LENGTH' in self.environ:
            self.environ['CONTENT_LENGTH'] = self.environ['HTTP_CONTENT_LENGTH']

        if 'HTTP_CONTENT_TYPE' in self.environ:
            self.environ['CONTENT_TYPE'] = self.environ['HTTP_CONTENT_TYPE']

        #setup required wsgi streams
        #self.environ['wsgi.input'] = WSGIInputStream(self, reader)
        self.environ['wsgi.errors'] = WSGIErrorStream()

        if not 'HTTP_HOST' in self.environ:
            if self.environ['HTTP_VERSION'] == 'HTTP/1.0':
                #ok in version 1.0, TODO what should host in wsgi environ be?
                host = 'localhost'
            else:
                raise HTTPError('Host header field is required in HTTP version > 1.0')
        else:
            host = self.environ['HTTP_HOST']

        if ':' in host:
            host, port = host.split(':')
        else:
            host, port = host, 80

        self.environ['SERVER_NAME'] = host
        self.environ['SERVER_PORT'] = port
        self.environ['SERVER_PROTOCOL'] = self.environ['HTTP_VERSION']

        self.response_headers = []
        self.response_status = httplib.OK
        self.response_exc_info = None

        #print self.environ

    def start_response(self, status, response_headers, exc_info = None):
        self.response_status = status
        self.response_headers = response_headers
        self.response_exc_info = exc_info

    @property
    def uri(self):
        return self.environ['REQUEST_URI']

    @property
    def version(self):
        return self.environ['HTTP_VERSION']

class HTTPConnection(object):

    def __init__(self, server, client_socket):
        self._server = server
        self._stream = BufferedStream(client_socket)
        #print 'new con'

    def _write_response(self, version, status, headers, response):

        if version == 'HTTP/1.0':
            chunked = False
        else:
            chunked = True

        headers.append(('Date', rfc822.formatdate()))
        headers.append(('Server', SERVER_ID))

        if chunked:
            headers.append(('Transfer-Encoding', 'chunked'))
        else:
            headers.append(('Content-length', str(len(response))))
            response = ''.join(response)

        with self._stream.get_writer() as writer:
            writer.clear()
            writer.write_bytes("%s %s\r\n" % (version, status))
            writer.write_bytes('\r\n'.join(["%s: %s" % (k, v) for k, v in headers]))
            writer.write_bytes("\r\n\r\n")

            if chunked:
                for chunk in response:
                    writer.write_bytes("%x;\r\n" % len(chunk))
                    writer.write_bytes(chunk)
                    writer.write_bytes("\r\n")
                writer.write_bytes("0\r\n\r\n")
            else:
                writer.write_bytes(response)

            writer.flush()

    def _read_request(self):

        with self._stream.get_reader() as reader:
            reader.fill() #initial fill
            parser = HTTPParser(reader.buffer)
            while True:
                #parse the buffer
                if parser.parse():
                    break #ok
                else:
                    #need more data from socket, could not parse request with data currently in buffer
                    reader.append() 
            return WSGIRequest(parser.environ)

    def _handle_request(self):
        request = self._read_request()
        response = self._server.handle_request(request)
        self._write_response(request.version, request.response_status, request.response_headers, response)  
        if request.version == 'HTTP/1.0':
            self._close()
        else:
            self._stream._stream.readable.notify(self.handle, 10)

    def _close(self):
        self._stream.close()

    def handle(self, has_timedout = False):
        if has_timedout:
            self._stream.close()
        else:
            Tasklet.defer(self._handle_request)

class WSGIServer(object):
    """A HTTP/1.1 Web server with WSGI application interface.

    Usage::

        def hello_world(environ, start_response):
            start_response("200 OK", [])
            return ["<html>Hello, world!</html>"]

        server = WSGIServer(hello_world)
        server.serve(('localhost', 8080))
    """
    log = logging.getLogger('WSGIServer')

    def __init__(self, application, request_log_level = logging.DEBUG):
        """Create a new WSGIServer serving the given *application*. Optionally
        the *request_log_level* can be given. This loglevel is used for logging the requests."""
        self._application = application
        self._request_log_level = request_log_level

    def internal_server_error(self, environ, start_response):
        """Default WSGI application for creating a default `500 Internal Server Error` response on any
        unhandled exception.
        The default response will render a traceback with a text/plain content-type.
        Can be overridden to provide a custom response."""
        start_response('500 Internal Server Error', [('Content-type', 'text/plain')])
        return [traceback.format_exc(20)]

    def handle_request(self, request):
        """All HTTP requests pass trough this method.
        This method provides a hook for logging, statistics and or further processing w.r.t. the *request*."""
        try:
            response = self._application(request.environ, request.start_response)
            self.log.log(self._request_log_level, "%s %s", request.response_status, request.uri)        
        except Exception:
            self.log.exception("unhandled exception while handling request")
            response = self.internal_server_error(request.environ, request.start_response)
        return response

    def handle_connection(self, client_socket):
        """All HTTP connections pass trough this method.
        This method provides a hook for logging, statistics and or further processing w.r.t. the connection."""
        HTTPConnection(self, client_socket).handle()

    def serve(self, endpoint):
        """Serves the application at the given *endpoint*. The *endpoint* must be a tuple (<host>, <port>)."""
        server_socket = Socket.server(endpoint)
        for client_socket in server_socket.accept_iter():
            self.handle_connection(client_socket)


