import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from config import Config


def create_app(config_class=Config):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app import state
        from elasticsearch import Elasticsearch
        from redis import Redis
        import rq

        if config_class.ELASTICSEARCH_URL:
            state.elasticsearch = Elasticsearch([config_class.ELASTICSEARCH_URL])
        state.redis_client = Redis.from_url(config_class.REDIS_URL)
        state.task_queue = rq.Queue('microblog-tasks', connection=state.redis_client)

        from app.db import init_db
        init_db(config_class.SQLALCHEMY_DATABASE_URI)

        yield

        if state.elasticsearch:
            state.elasticsearch.close()

    app = FastAPI(lifespan=lifespan)

    app.add_middleware(SessionMiddleware, secret_key=config_class.SECRET_KEY)
    app.mount('/static', StaticFiles(directory='app/static'), name='static')

    from app.templates import setup_templates
    setup_templates(app)

    from app.auth import router as auth_router
    from app.main import router as main_router
    from app.api import router as api_router

    app.include_router(auth_router, prefix='/auth')
    app.include_router(main_router)
    app.include_router(api_router, prefix='/api')

    from app.errors.handlers import register_exception_handlers
    register_exception_handlers(app)

    if not getattr(config_class, 'TESTING', False):
        _configure_logging(app, config_class)

    return app


def _configure_logging(app: FastAPI, config_class) -> None:
    if config_class.MAIL_SERVER:
        auth = None
        if config_class.MAIL_USERNAME or config_class.MAIL_PASSWORD:
            auth = (config_class.MAIL_USERNAME, config_class.MAIL_PASSWORD)
        secure = () if config_class.MAIL_USE_TLS else None
        mail_handler = SMTPHandler(
            mailhost=(config_class.MAIL_SERVER, config_class.MAIL_PORT),
            fromaddr=f'no-reply@{config_class.MAIL_SERVER}',
            toaddrs=config_class.ADMINS,
            subject='Microblog Failure',
            credentials=auth,
            secure=secure)
        mail_handler.setLevel(logging.ERROR)
        logging.getLogger('uvicorn').addHandler(mail_handler)

    if config_class.LOG_TO_STDOUT:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        logging.getLogger('uvicorn').addHandler(stream_handler)
    else:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/microblog.log',
                                           maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        logging.getLogger('uvicorn').addHandler(file_handler)
