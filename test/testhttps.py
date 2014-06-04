# coding: utf-8
# Created on 2014-6-4
# Author: J.

from concurrence.http import HTTPSConnection, try_getresponse
import unittest

class TestHTTPS(unittest.TestCase):
    def testGet(self):
        #100 17533.1379395
        #1000 167142.894043
        host = 'www.google.com:443'
        uri = '/'
        cnn = HTTPSConnection(host)
        cnn.connect(timeout=3)
        cnn.request('GET', uri)
        response = try_getresponse(cnn)
        print response.read()
    
if __name__ == '__main__':
    unittest.main(timeout = 100.0)