from concurrence import unittest, Tasklet
import os

class TestTest(unittest.TestCase):
    def testTimeout(self):
        try:
            Tasklet.sleep(4)
            self.fail('expected timeout!')
        except TaskletExit:
            pass #caused by timeout

def ontimeout():
    os._exit(0)

if __name__ == '__main__':
    unittest.main(timeout = 2, ontimeout = ontimeout)
