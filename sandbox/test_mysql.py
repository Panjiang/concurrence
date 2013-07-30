from concurrence import dispatch, Tasklet
from concurrence.database.mysql import client, dbapi, PacketReadError

DB_HOST = 'localhost'
DB_USER = 'concurrence_test'
DB_PASSWD = 'concurrence_test'
DB_DB = 'concurrence_test'

def main():
    cnn = client.connect(host = DB_HOST, user = DB_USER, passwd = DB_PASSWD, db = DB_DB)
    i = 0
    while True:
        i += 1
        res = cnn.query("select %d" % i)
        print list(res)[0][0]
        res.close()
        Tasklet.sleep(1)

if __name__ == '__main__':
    dispatch(main)
