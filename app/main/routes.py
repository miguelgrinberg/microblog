from datetime import datetime, timezone
import sqlalchemy as sa
from fastapi import Depends, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from langdetect import detect, LangDetectException
from sqlalchemy.orm import Session

from app.main import router
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm, MessageForm
from app.db import get_db, paginate, first_or_404
from app.i18n import _, get_locale
from app.models import User, Post, Message, Notification
from app.security import flash, get_current_user
from app.templates import render
from app.translate import translate as do_translate
from config import Config


def _require_login(request: Request, db: Session):
    user = get_current_user(request, db)
    if user is None:
        return None, RedirectResponse(url=f'/auth/login?next={request.url.path}', status_code=303)
    return user, None


def _update_last_seen(current_user, db: Session) -> None:
    current_user.last_seen = datetime.now(timezone.utc)
    db.commit()


@router.api_route('/', methods=['GET', 'POST'], response_class=HTMLResponse, name='index')
@router.api_route('/index', methods=['GET', 'POST'], response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    form_data = await request.form() if request.method == 'POST' else None
    form = PostForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        try:
            language = detect(form.post.data)
        except LangDetectException:
            language = ''
        post = Post(body=form.post.data, author=current_user, language=language)
        db.add(post)
        db.commit()
        flash(request, _('Your post is now live!'))
        return RedirectResponse(url='/', status_code=303)

    page = int(request.query_params.get('page', 1))
    posts = paginate(db, current_user.following_posts(), page=page,
                     per_page=Config.POSTS_PER_PAGE)
    next_url = str(request.url_for('index').include_query_params(page=posts.next_num)) \
        if posts.has_next else None
    prev_url = str(request.url_for('index').include_query_params(page=posts.prev_num)) \
        if posts.has_prev else None
    return render(request, db, 'index.html', title=_('Home'), form=form,
                  posts=posts.items, next_url=next_url, prev_url=prev_url)


@router.get('/explore', response_class=HTMLResponse, name='explore')
async def explore(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    page = int(request.query_params.get('page', 1))
    query = sa.select(Post).order_by(Post.timestamp.desc())
    posts = paginate(db, query, page=page, per_page=Config.POSTS_PER_PAGE)
    next_url = str(request.url_for('explore').include_query_params(page=posts.next_num)) \
        if posts.has_next else None
    prev_url = str(request.url_for('explore').include_query_params(page=posts.prev_num)) \
        if posts.has_prev else None
    return render(request, db, 'index.html', title=_('Explore'),
                  posts=posts.items, next_url=next_url, prev_url=prev_url)


@router.get('/user/{username}', response_class=HTMLResponse, name='user')
async def user(username: str, request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    profile_user = first_or_404(db, sa.select(User).where(User.username == username))
    page = int(request.query_params.get('page', 1))
    query = profile_user.posts.select().order_by(Post.timestamp.desc())
    posts = paginate(db, query, page=page, per_page=Config.POSTS_PER_PAGE)
    next_url = str(request.url_for('user', username=username).include_query_params(
        page=posts.next_num)) if posts.has_next else None
    prev_url = str(request.url_for('user', username=username).include_query_params(
        page=posts.prev_num)) if posts.has_prev else None
    form = EmptyForm(meta={'session': request.session})
    return render(request, db, 'user.html', user=profile_user, posts=posts.items,
                  next_url=next_url, prev_url=prev_url, form=form)


@router.get('/user/{username}/popup', response_class=HTMLResponse, name='user_popup')
async def user_popup(username: str, request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    profile_user = first_or_404(db, sa.select(User).where(User.username == username))
    form = EmptyForm(meta={'session': request.session})
    return render(request, db, 'user_popup.html', user=profile_user, form=form)


@router.api_route('/edit_profile', methods=['GET', 'POST'],
                  response_class=HTMLResponse, name='edit_profile')
async def edit_profile(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    form_data = await request.form() if request.method == 'POST' else None
    form = EditProfileForm(current_user.username,
                           formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.commit()
        flash(request, _('Your changes have been saved.'))
        return RedirectResponse(url='/edit_profile', status_code=303)
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me

    return render(request, db, 'edit_profile.html', title=_('Edit Profile'), form=form)


@router.post('/follow/{username}', name='follow')
async def follow(username: str, request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    form_data = await request.form()
    form = EmptyForm(formdata=form_data, meta={'session': request.session})
    if form.validate():
        target = db.scalar(sa.select(User).where(User.username == username))
        if target is None:
            flash(request, _('User %(username)s not found.', username=username))
            return RedirectResponse(url='/', status_code=303)
        if target == current_user:
            flash(request, _('You cannot follow yourself!'))
            return RedirectResponse(url=f'/user/{username}', status_code=303)
        current_user.follow(target)
        db.commit()
        flash(request, _('You are following %(username)s!', username=username))
    return RedirectResponse(url=f'/user/{username}', status_code=303)


@router.post('/unfollow/{username}', name='unfollow')
async def unfollow(username: str, request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    form_data = await request.form()
    form = EmptyForm(formdata=form_data, meta={'session': request.session})
    if form.validate():
        target = db.scalar(sa.select(User).where(User.username == username))
        if target is None:
            flash(request, _('User %(username)s not found.', username=username))
            return RedirectResponse(url='/', status_code=303)
        if target == current_user:
            flash(request, _('You cannot unfollow yourself!'))
            return RedirectResponse(url=f'/user/{username}', status_code=303)
        current_user.unfollow(target)
        db.commit()
        flash(request, _('You are not following %(username)s.', username=username))
    return RedirectResponse(url=f'/user/{username}', status_code=303)


@router.post('/translate', name='translate_text')
async def translate_text(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return JSONResponse({'error': 'unauthorized'}, status_code=401)
    data = await request.json()
    return {'text': do_translate(data['text'], data['source_language'], data['dest_language'])}


@router.get('/search', response_class=HTMLResponse, name='search')
async def search(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    search_form = SearchForm(formdata=request.query_params)
    if not search_form.validate():
        return RedirectResponse(url='/explore', status_code=303)

    page = int(request.query_params.get('page', 1))
    posts, total = Post.search(search_form.q.data, page, Config.POSTS_PER_PAGE)
    q = search_form.q.data
    next_url = str(request.url_for('search').include_query_params(q=q, page=page + 1)) \
        if total > page * Config.POSTS_PER_PAGE else None
    prev_url = str(request.url_for('search').include_query_params(q=q, page=page - 1)) \
        if page > 1 else None
    return render(request, db, 'search.html', title=_('Search'),
                  posts=posts, next_url=next_url, prev_url=prev_url)


@router.api_route('/send_message/{recipient}', methods=['GET', 'POST'],
                  response_class=HTMLResponse, name='send_message')
async def send_message(recipient: str, request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    recipient_user = first_or_404(db, sa.select(User).where(User.username == recipient))
    form_data = await request.form() if request.method == 'POST' else None
    form = MessageForm(formdata=form_data, meta={'session': request.session})

    if request.method == 'POST' and form.validate():
        msg = Message(author=current_user, recipient=recipient_user, body=form.message.data)
        db.add(msg)
        recipient_user.add_notification('unread_message_count',
                                        recipient_user.unread_message_count())
        db.commit()
        flash(request, _('Your message has been sent.'))
        return RedirectResponse(url=f'/user/{recipient}', status_code=303)

    return render(request, db, 'send_message.html', title=_('Send Message'),
                  form=form, recipient=recipient)


@router.get('/messages', response_class=HTMLResponse, name='messages')
async def messages(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    _update_last_seen(current_user, db)

    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.commit()

    page = int(request.query_params.get('page', 1))
    query = current_user.messages_received.select().order_by(Message.timestamp.desc())
    msgs = paginate(db, query, page=page, per_page=Config.POSTS_PER_PAGE)
    next_url = str(request.url_for('messages').include_query_params(page=msgs.next_num)) \
        if msgs.has_next else None
    prev_url = str(request.url_for('messages').include_query_params(page=msgs.prev_num)) \
        if msgs.has_prev else None
    return render(request, db, 'messages.html', messages=msgs.items,
                  next_url=next_url, prev_url=prev_url)


@router.get('/export_posts', name='export_posts')
async def export_posts(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return redir
    if current_user.get_task_in_progress('export_posts'):
        flash(request, _('An export task is currently in progress'))
    else:
        current_user.launch_task('export_posts', _('Exporting posts...'))
        db.commit()
    return RedirectResponse(url=f'/user/{current_user.username}', status_code=303)


@router.get('/notifications', name='notifications')
async def notifications(request: Request, db: Session = Depends(get_db)):
    current_user, redir = _require_login(request, db)
    if redir:
        return JSONResponse({'error': 'unauthorized'}, status_code=401)
    since = float(request.query_params.get('since', 0.0))
    query = current_user.notifications.select().where(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    notifs = db.scalars(query)
    return [{'name': n.name, 'data': n.get_data(), 'timestamp': n.timestamp}
            for n in notifs]
