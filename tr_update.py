#!flask/bin/python
import os
import sys
if sys.platform == 'win32':
    pybabel = 'flask\\Scripts\\pybabel'
else:
    pybabel = 'flask/bin/pybabel'
os.system(pybabel + ' extract -F babel.cfg -k lazy_gettext -o messages.pot app')
os.system(pybabel + ' update -i messages.pot -d app/translations')
os.unlink('messages.pot')
