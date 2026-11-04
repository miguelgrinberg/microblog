import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_moment import Moment
from flask_babel import Babel, lazy_gettext as _l
from elasticsearch import Elasticsearch
from redis import Redis
import rq
from config import Config
from app.privacy.secure_logging import make_secure_handler


def get_locale():
    return request.accept_languages.best_match(current_app.config['LANGUAGES'])


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = _l('Please log in to access this page.')
mail = Mail()
moment = Moment()
babel = Babel()


def create_app(config_class=Config):
    # РЕФАКТОРИНГ (Завд.4): Cognitive Complexity знижено з 18 до ~2
    # шляхом Extract Method — логіку розбито на три незалежні кроки.
    app = Flask(__name__)
    app.config.from_object(config_class)
    # ЛР4: стабільний порядок полів JSON = порядок контракту (метадані першими)
    app.json.sort_keys = False

    _init_extensions(app)
    _register_blueprints(app)
    _configure_logging(app)

    # ЛР4: централізоване безпечне логування діє в УСІХ режимах
    from app.privacy import secure_logging
    secure_logging.init_app(app)

    return app


def _init_extensions(app):
    """Ініціалізація Flask-розширень (Extract Method)."""
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    app.elasticsearch = Elasticsearch([app.config['ELASTICSEARCH_URL']]) \
        if app.config['ELASTICSEARCH_URL'] else None
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.task_queue = rq.Queue('microblog-tasks', connection=app.redis)


def _register_blueprints(app):
    """Реєстрація blueprint-ів (Extract Method)."""
    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.cli import bp as cli_bp
    app.register_blueprint(cli_bp)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')


def _configure_logging(app):
    """Налаштування логування. Guard Clause прибирає перший рівень
    вкладеності: у debug/testing-режимі логування не потрібне."""
    if app.testing:
        return
    if app.debug:
        # ЛР4: у debug дозволяємо безпечний stdout-лог (для live demo)
        if app.config['LOG_TO_STDOUT']:
            _configure_file_or_stdout_logging(app)
        return

    _configure_mail_logging(app)
    _configure_file_or_stdout_logging(app)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Microblog startup')


def _configure_mail_logging(app):
    """Guard Clause замість вкладеного if — email-логування (Extract Method)."""
    if not app.config['MAIL_SERVER']:
        return

    auth = None
    if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
        auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
    secure = () if app.config['MAIL_USE_TLS'] else None

    mail_handler = SMTPHandler(
        mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
        fromaddr='no-reply@' + app.config['MAIL_SERVER'],
        toaddrs=app.config['ADMINS'], subject='Microblog Failure',
        credentials=auth, secure=secure)
    make_secure_handler(mail_handler)  # листи адміну теж без PII/секретів
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)


def _configure_file_or_stdout_logging(app):
    """Guard Clause замість if/else — файлове чи stdout логування (Extract Method)."""
    if app.config['LOG_TO_STDOUT']:
        stream_handler = make_secure_handler(
            logging.StreamHandler(), app.config.get('LOG_FORMAT', 'text'))
        stream_handler.setLevel(logging.INFO)
        from flask.logging import default_handler
        app.logger.removeHandler(default_handler)  # без дублювання рядків
        app.logger.addHandler(stream_handler)
        return

    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = make_secure_handler(
        RotatingFileHandler('logs/microblog.log', maxBytes=10240,
                            backupCount=10),
        app.config.get('LOG_FORMAT', 'text'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)


from app import models
