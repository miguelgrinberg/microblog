from datetime import datetime, timezone, timedelta
from hashlib import md5
import json
import secrets
from time import time
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from app.db import Base, get_db_session
from app.search import add_to_index, remove_from_index, query_index


class SearchableMixin:
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return [], 0
        when = [(ids[i], i) for i in range(len(ids))]
        db = get_db_session()
        query = sa.select(cls).where(cls.id.in_(ids)).order_by(
            sa.case(*when, value=cls.id))
        return db.scalars(query), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        db = get_db_session()
        for obj in db.scalars(sa.select(cls)):
            add_to_index(cls.__tablename__, obj)


sa.event.listen(so.Session, 'before_commit', SearchableMixin.before_commit)
sa.event.listen(so.Session, 'after_commit', SearchableMixin.after_commit)


class PaginatedAPIMixin:
    @staticmethod
    def to_collection_dict(query, db, page, per_page, url_builder):
        from app.db import paginate
        resources = paginate(db, query, page=page, per_page=per_page)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_builder(page=page, per_page=per_page),
                'next': url_builder(page=page + 1, per_page=per_page) if resources.has_next else None,
                'prev': url_builder(page=page - 1, per_page=per_page) if resources.has_prev else None,
            }
        }
        return data


followers = sa.Table(
    'followers',
    Base.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True)
)


class User(PaginatedAPIMixin, Base):
    __tablename__ = 'user'

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    last_message_read_time: so.Mapped[Optional[datetime]]
    token: so.Mapped[Optional[str]] = so.mapped_column(sa.String(32), index=True, unique=True)
    token_expiration: so.Mapped[Optional[datetime]]

    posts: so.WriteOnlyMapped['Post'] = so.relationship(back_populates='author')
    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers')
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following')
    messages_sent: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.sender_id', back_populates='author')
    messages_received: so.WriteOnlyMapped['Message'] = so.relationship(
        foreign_keys='Message.recipient_id', back_populates='recipient')
    notifications: so.WriteOnlyMapped['Notification'] = so.relationship(back_populates='user')
    tasks: so.WriteOnlyMapped['Task'] = so.relationship(back_populates='user')

    def __repr__(self):
        return f'<User {self.username}>'

    # --- auth ---

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def avatar(self, size: int) -> str:
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'

    # --- follow ---

    def follow(self, user: 'User') -> None:
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user: 'User') -> None:
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user: 'User') -> bool:
        db = get_db_session()
        query = self.following.select().where(User.id == user.id)
        return db.scalar(query) is not None

    def followers_count(self) -> int:
        db = get_db_session()
        query = sa.select(sa.func.count()).select_from(
            self.followers.select().subquery())
        return db.scalar(query)

    def following_count(self) -> int:
        db = get_db_session()
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery())
        return db.scalar(query)

    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return (
            sa.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(
                Follower.id == self.id,
                Author.id == self.id,
            ))
            .group_by(Post)
            .order_by(Post.timestamp.desc())
        )

    def posts_count(self) -> int:
        db = get_db_session()
        query = sa.select(sa.func.count()).select_from(
            self.posts.select().subquery())
        return db.scalar(query)

    # --- password reset ---

    def get_reset_password_token(self, expires_in: int = 600) -> str:
        from config import Config
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            Config.SECRET_KEY, algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token: str) -> Optional['User']:
        from config import Config
        try:
            id = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])['reset_password']
        except Exception:
            return None
        return get_db_session().get(User, id)

    # --- messages ---

    def unread_message_count(self) -> int:
        db = get_db_session()
        last_read_time = self.last_message_read_time or datetime(1900, 1, 1)
        query = sa.select(Message).where(
            Message.recipient == self,
            Message.timestamp > last_read_time)
        return db.scalar(sa.select(sa.func.count()).select_from(query.subquery()))

    def add_notification(self, name: str, data) -> 'Notification':
        db = get_db_session()
        db.execute(self.notifications.delete().where(Notification.name == name))
        n = Notification(name=name, payload_json=json.dumps(data), user=self)
        db.add(n)
        return n

    # --- background tasks ---

    def launch_task(self, name: str, description: str, *args, **kwargs) -> 'Task':
        from app import state
        rq_job = state.task_queue.enqueue(
            f'app.tasks.{name}', self.id, *args, **kwargs)
        db = get_db_session()
        task = Task(id=rq_job.get_id(), name=name,
                    description=description, user=self)
        db.add(task)
        return task

    def get_tasks_in_progress(self):
        db = get_db_session()
        query = self.tasks.select().where(Task.complete == False)
        return db.scalars(query)

    def get_task_in_progress(self, name: str) -> Optional['Task']:
        db = get_db_session()
        query = self.tasks.select().where(Task.name == name,
                                          Task.complete == False)
        return db.scalar(query)

    # --- API ---

    def to_dict(self, include_email: bool = False) -> dict:
        from app.i18n import get_locale
        data = {
            'id': self.id,
            'username': self.username,
            'last_seen': self.last_seen.replace(tzinfo=timezone.utc).isoformat() if self.last_seen else None,
            'about_me': self.about_me,
            'post_count': self.posts_count(),
            'follower_count': self.followers_count(),
            'following_count': self.following_count(),
            '_links': {
                'self': f'/api/users/{self.id}',
                'followers': f'/api/users/{self.id}/followers',
                'following': f'/api/users/{self.id}/following',
                'avatar': self.avatar(128),
            }
        }
        if include_email:
            data['email'] = self.email
        return data

    def from_dict(self, data: dict, new_user: bool = False) -> None:
        for field in ['username', 'email', 'about_me']:
            if field in data:
                setattr(self, field, data[field])
        if new_user and 'password' in data:
            self.set_password(data['password'])

    def get_token(self, expires_in: int = 3600) -> str:
        db = get_db_session()
        now = datetime.now(timezone.utc)
        if self.token and self.token_expiration.replace(
                tzinfo=timezone.utc) > now + timedelta(seconds=60):
            return self.token
        self.token = secrets.token_hex(16)
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.add(self)
        return self.token

    def revoke_token(self) -> None:
        self.token_expiration = datetime.now(timezone.utc) - timedelta(seconds=1)

    @staticmethod
    def check_token(token: str) -> Optional['User']:
        db = get_db_session()
        user = db.scalar(sa.select(User).where(User.token == token))
        if user is None or user.token_expiration.replace(
                tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        return user


class Post(SearchableMixin, Base):
    __tablename__ = 'post'
    __searchable__ = ['body']

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    language: so.Mapped[Optional[str]] = so.mapped_column(sa.String(5))

    author: so.Mapped[User] = so.relationship(back_populates='posts')

    def __repr__(self):
        return f'<Post {self.body}>'


class Message(Base):
    __tablename__ = 'message'

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    sender_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    recipient_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))

    author: so.Mapped[User] = so.relationship(
        foreign_keys='Message.sender_id', back_populates='messages_sent')
    recipient: so.Mapped[User] = so.relationship(
        foreign_keys='Message.recipient_id', back_populates='messages_received')

    def __repr__(self):
        return f'<Message {self.body}>'


class Notification(Base):
    __tablename__ = 'notification'

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    timestamp: so.Mapped[float] = so.mapped_column(index=True, default=time)
    payload_json: so.Mapped[str] = so.mapped_column(sa.Text)

    user: so.Mapped[User] = so.relationship(back_populates='notifications')

    def get_data(self):
        return json.loads(str(self.payload_json))


class Task(Base):
    __tablename__ = 'task'

    id: so.Mapped[str] = so.mapped_column(sa.String(36), primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(128), index=True)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id))
    complete: so.Mapped[bool] = so.mapped_column(default=False)

    user: so.Mapped[User] = so.relationship(back_populates='tasks')

    def get_rq_job(self):
        import redis
        import rq
        from app import state
        try:
            return rq.job.Job.fetch(self.id, connection=state.redis_client)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None

    def get_progress(self) -> int:
        job = self.get_rq_job()
        return job.meta.get('progress', 0) if job is not None else 100
