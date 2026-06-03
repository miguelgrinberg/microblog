import json
import sys
import time
import sqlalchemy as sa
from jinja2 import Environment, FileSystemLoader
from rq import get_current_job
from sqlalchemy.orm import Session

from app.db import get_engine
from app.email import send_email
from config import Config


def _get_db():
    return Session(get_engine())


def _render(template_name: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader('app/templates'))
    return env.get_template(template_name).render(**ctx)


def _set_task_progress(db: Session, progress: int) -> None:
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        from app.models import Task
        task = db.get(Task, job.get_id())
        if task:
            task.user.add_notification('task_progress',
                                       {'task_id': job.get_id(), 'progress': progress})
            if progress >= 100:
                task.complete = True
            db.commit()


def export_posts(user_id: int) -> None:
    from app.models import User, Post, Task

    db = _get_db()
    # Wire up the db session ContextVar so model methods work
    from app.db import _db_session_var
    token = _db_session_var.set(db)
    try:
        user = db.get(User, user_id)
        _set_task_progress(db, 0)
        data = []
        i = 0
        total_posts = db.scalar(sa.select(sa.func.count()).select_from(
            user.posts.select().subquery()))
        for post in db.scalars(user.posts.select().order_by(Post.timestamp.asc())):
            data.append({'body': post.body,
                         'timestamp': post.timestamp.isoformat() + 'Z'})
            time.sleep(5)
            i += 1
            _set_task_progress(db, 100 * i // total_posts)

        send_email(
            '[Microblog] Your blog posts',
            sender=Config.ADMINS[0],
            recipients=[user.email],
            text_body=_render('email/export_posts.txt', user=user),
            html_body=_render('email/export_posts.html', user=user),
            attachments=[('posts.json', 'application/json',
                          json.dumps({'posts': data}, indent=4))],
            sync=True)
    except Exception:
        _set_task_progress(db, 100)
        import logging
        logging.getLogger(__name__).error('Unhandled exception', exc_info=sys.exc_info())
    finally:
        _set_task_progress(db, 100)
        _db_session_var.reset(token)
        db.close()
