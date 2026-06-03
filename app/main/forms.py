import sqlalchemy as sa
from wtforms import Form, StringField, SubmitField, TextAreaField
from wtforms.validators import ValidationError, DataRequired, Length
from wtforms.csrf.session import SessionCSRF
from app.i18n import _l
from config import Config


class BaseForm(Form):
    class Meta:
        csrf = True
        csrf_class = SessionCSRF
        csrf_secret = Config.SECRET_KEY.encode()


class EditProfileForm(BaseForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    about_me = TextAreaField(_l('About me'), validators=[Length(min=0, max=140)])
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            from app.db import get_db_session
            from app.models import User
            user = get_db_session().scalar(sa.select(User).where(User.username == username.data))
            if user is not None:
                raise ValidationError(_l('Please use a different username.'))


class EmptyForm(BaseForm):
    submit = SubmitField('Submit')


class PostForm(BaseForm):
    post = TextAreaField(_l('Say something'), validators=[
        DataRequired(), Length(min=1, max=140)])
    submit = SubmitField(_l('Submit'))


class SearchForm(Form):
    q = StringField(_l('Search'), validators=[DataRequired()])

    class Meta:
        csrf = False


class MessageForm(BaseForm):
    message = TextAreaField(_l('Message'), validators=[
        DataRequired(), Length(min=1, max=140)])
    submit = SubmitField(_l('Submit'))
