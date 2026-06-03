from contextvars import ContextVar
from typing import Generator, Optional
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Session
from fastapi import HTTPException


class Base(DeclarativeBase):
    pass


_engine = None
_db_session_var: ContextVar[Optional[Session]] = ContextVar('db_session', default=None)


def init_db(database_url: str):
    global _engine
    from sqlalchemy import create_engine
    _engine = create_engine(database_url)


def get_engine():
    global _engine
    if _engine is None:
        from config import Config
        from sqlalchemy import create_engine
        _engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    return _engine


def get_db_session() -> Session:
    session = _db_session_var.get()
    if session is None:
        raise RuntimeError('No database session in context')
    return session


def get_db() -> Generator[Session, None, None]:
    engine = get_engine()
    with Session(engine) as session:
        token = _db_session_var.set(session)
        try:
            yield session
        finally:
            _db_session_var.reset(token)


class Pagination:
    def __init__(self, items, total: int, page: int, per_page: int):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = (total + per_page - 1) // per_page if total > 0 else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None


def paginate(db: Session, query, page: int, per_page: int, error_out: bool = False) -> Pagination:
    count_query = sa.select(sa.func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0
    items = list(db.scalars(query.offset((page - 1) * per_page).limit(per_page)).all())
    return Pagination(items, total, page, per_page)


def get_or_404(db: Session, model, ident):
    obj = db.get(model, ident)
    if obj is None:
        raise HTTPException(status_code=404)
    return obj


def first_or_404(db: Session, query):
    obj = db.scalar(query)
    if obj is None:
        raise HTTPException(status_code=404)
    return obj
