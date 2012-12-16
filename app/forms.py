from flask.ext.wtf import Form, TextField, BooleanField
from flask.ext.wtf import Required

class LoginForm(Form):
    openid = TextField('openid', validators = [Required()])
    remember_me = BooleanField('remember_me', default = False)
    