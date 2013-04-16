#!/usr/bin/python
import os, subprocess, sys
subprocess.call(['python', 'virtualenv.py', 'flask'])
if sys.platform == 'win32':
    bin = 'Scripts'
else:
    bin = 'bin'
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-login'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-openid'])
if sys.platform == 'win32':
    subprocess.call([os.path.join('flask', bin, 'pip'), 'install', '--no-deps', 'lamson', 'chardet', 'flask-mail'])
else:
    subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-mail'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'sqlalchemy==0.7.9'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-sqlalchemy'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'sqlalchemy-migrate'])
if sys.platform != 'win32':
    subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'mysql-python'])
#subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-whooshalchemy'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'git+git://github.com/miguelgrinberg/Flask-WhooshAlchemy'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-wtf'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flask-babel'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'guess-language'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'flup'])
subprocess.call([os.path.join('flask', bin, 'pip'), 'install', 'coverage'])
