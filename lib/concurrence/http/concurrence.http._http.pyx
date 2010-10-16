# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence.io._io cimport Buffer
from concurrence.io._io import BufferUnderflowError

cdef extern from "http11_parser.h":
    ctypedef struct http_parser
    ctypedef int size_t

    int http_parser_init(http_parser *parser)
    int http_parser_finish(http_parser *parser)
    size_t http_parser_execute(http_parser *parser, char *data, size_t len, size_t off)
    int http_parser_has_error(http_parser *parser)
    int http_parser_is_finished(http_parser *parser)

ctypedef void (*element_cb)(void *data, char *at, size_t length)
ctypedef void (*field_cb)(void *data, char *field, size_t flen, char *value, size_t vlen)

cdef extern from "http11_parser_alloc.h":
    http_parser *http_parser_alloc(void *obj, element_cb request_method,
                                              element_cb request_uri,
                                              element_cb fragment,
                                              element_cb request_path,
                                              element_cb query_string,
                                              element_cb http_version,
                                              element_cb header_done,
                                              field_cb field)
    void http_parser_free(http_parser *)

cdef extern from "Python.h":
    object PyString_FromStringAndSize(char *, int)

cdef class HTTPParser

cdef void cb_request_method(void *data, char *at, size_t length):
    (<HTTPParser>data)._cb_request_method(PyString_FromStringAndSize(at, length))

cdef void cb_request_uri(void *data, char *at, size_t length):
    (<HTTPParser>data)._cb_request_uri(PyString_FromStringAndSize(at, length))

#cdef void cb_fragment(void *data, char *at, size_t length):
#    (<HTTPParser>data)._cb_fragment(PyString_FromStringAndSize(at, length))
#    unused for now, fragment is not part of cgi spec

cdef void cb_request_path(void *data, char *at, size_t length):
    (<HTTPParser>data)._cb_request_path(PyString_FromStringAndSize(at, length))

cdef void cb_query_string(void *data, char *at, size_t length):
    (<HTTPParser>data)._cb_query_string(PyString_FromStringAndSize(at, length))

cdef void cb_http_version(void *data, char *at, size_t length):
    (<HTTPParser>data)._cb_http_version(PyString_FromStringAndSize(at, length))

#cdef void cb_header_done(void *data, char *at, size_t length):
#    #(<HTTPParser>data)._cb_header_done(PyString_FromStringAndSize(at, length))
#    pass #unused

cdef void cb_field(void *data, char *field, size_t flen, char *value, size_t vlen):
    (<HTTPParser>data)._cb_field(PyString_FromStringAndSize(field, flen), PyString_FromStringAndSize(value, vlen))

class HTTPParserError(Exception):
    pass

cdef class HTTPParser:
    """
    """
    cdef http_parser *_parser
    cdef Buffer _buffer
    cdef readonly environ

    def __cinit__(self, Buffer buffer):
        self._parser = http_parser_alloc(<void *>self, cb_request_method, cb_request_uri, NULL, cb_request_path, cb_query_string,cb_http_version, NULL, cb_field)
        http_parser_init(self._parser)

    def __init__(self, Buffer buffer):
        self._buffer = buffer
        self.environ = {}

    def __dealloc__(self):
        http_parser_free(self._parser)

    cdef _cb_request_method(self, method):
        self.environ['REQUEST_METHOD'] = method

    cdef _cb_query_string(self, qs):
        self.environ['QUERY_STRING'] = qs

    cdef _cb_request_path(self, path):
        self.environ['PATH_INFO'] = path

#    cdef _cb_fragment(self, fragment):
#        pass #unused, not part of cgi spec

    cdef _cb_request_uri(self, uri):
        self.environ['REQUEST_URI'] = uri

    cdef _cb_http_version(self, version):
        self.environ['HTTP_VERSION'] = version

#    cdef _cb_header_done(self, hd):
#        pass #unused

    cdef _cb_field(self, name, value):
        key = 'HTTP_' + name
        if key in self.environ:
            self.environ[key] = self.environ[key] + ',' + value # comma-separate multiple headers
        else:
            self.environ[key] = value

    def parse(self):
        cdef size_t nread
        cdef int remaining
        if http_parser_is_finished(self._parser):
            raise HTTPParserError("cannot parse: parser already finished")
        elif http_parser_has_error(self._parser):
            raise HTTPParserError("cannot parse: parser already finished with error")
        remaining = self._buffer._remaining()
        if remaining > 0:
            nread = http_parser_execute(self._parser, <char *>self._buffer._buff, remaining, self._buffer._position)
            if http_parser_has_error(self._parser):
                raise HTTPParserError("parse error")
            else:
                self._buffer._position = self._buffer._position + nread
                if http_parser_is_finished(self._parser):
                    return True
                else:
                    return False
        else:
            raise BufferUnderflowError()

    def is_finished(self):
        if http_parser_is_finished(self._parser):
            return True
        else:
            return False

    def has_error(self):
        if http_parser_has_error(self._parser):
            return True
        else:
            return False

