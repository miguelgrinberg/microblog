#!flask/bin/python

# use mysql
os.environ['SQLALCHEMY_DATABASE_URI'] = 'mysql://apps:apps@localhost/apps'

from flup.server.fcgi import WSGIServer
from app import app

if __name__ == '__main__':
    WSGIServer(app).run()
