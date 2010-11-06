from stackless import *
import adns
import sys

class QueryEngine(object):
    """
    Usage:
    create 1: engine = QueryEngine()
    create 2: engine = QueryEngine(configtext="nameserver 8.8.8.8")
    sync query: result = engine.synchronous("www.google.com", adns.rr.ADDR)
    run async engine: engine.run()
    async query: result = engine.asynchronous("www.google.com", adns.rr.ADDR)
    """
    def __init__(self, s=None, configtext=None):
        if s is None:
            flags = adns.iflags.noautosys | adns.iflags.noserverwarn | adns.iflags.noerrprint
            if configtext is None:
                s = adns.init(flags)
            else:
                s = adns.init(flags, sys.stderr, configtext)
        self._s = s
        self._queries = {}
        self._command_channel = stackless.channel()

    def synchronous(self, qname, rr, flags=0):
        return self._s.synchronous(qname, rr, flags)

    def asynchronous(self, qname, rr, flags=0):
        response_channel = stackless.channel()
        self._command_channel.send((qname, rr, flags, response_channel))
        return response_channel.receive()

    def run(self):
        stackless.tasklet(self._run)()

    def _run(self):
        while True:
            # if no pending queries, blocking on channel
            while not len(self._queries) or self._command_channel.balance > 0:
                qname, rr, flags, response_channel = self._command_channel.receive()
                q = self._s.submit(qname, rr, flags)
                self._queries[q] = response_channel
            for q in self._s.completed(0):
                answer = q.check()
                response_channel = self._queries[q]
                del self._queries[q]
                response_channel.send(answer)
            stackless.schedule()
