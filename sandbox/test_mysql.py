from concurrence import dispatch, Tasklet
from concurrence.database.mysql import client, dbapi, PacketReadError
import logging
import traceback

modlogger = logging.getLogger("")
modlogger.setLevel(logging.DEBUG)
stderr_channel = logging.StreamHandler()
stderr_channel.setLevel(logging.DEBUG)
modlogger.addHandler(stderr_channel)

DB_HOST = 'localhost'
DB_USER = 'concurrence_test'
DB_PASSWD = 'concurrence_test'
DB_DB = 'concurrence_test'

def main():
    i = 0
    cnn = None
    while True:
        try:
            print "iteration"
            if not cnn or not cnn.is_connected():
                cnn = client.connect(host = DB_HOST, user = DB_USER, passwd = DB_PASSWD, db = DB_DB)
            res = cnn.query("select %d" % i)
            print list(res)[0][0]
            res.close()
            res = cnn.query("select sleep(1)")
            list(res)[0][0]
            res.close()
        except Exception as e:
            traceback.print_exc()
        else:
            i += 1

if __name__ == '__main__':
    dispatch(main)
