import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Post, Message, Notification, Task

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Post': Post,
            'Message': Message, 'Notification': Notification, 'Task': Task}


def create_initial_data():
    """首次运行时创建初始数据"""
    with app.app_context():
        # 检查是否已存在admin用户
        admin = db.session.scalar(sa.select(User).where(User.username == 'admin'))
        if not admin:
            # 创建admin用户
            admin = User(username='admin', email='admin@example.com')
            admin.set_password('admin')  # 设置默认密码为admin
            db.session.add(admin)
            db.session.commit()
            
            # 创建第一条博客
            post = Post(body='这是第一条博客', author=admin)
            db.session.add(post)
            db.session.commit()
            print('初始数据创建成功：已创建admin用户和第一条博客')


# 检查并创建初始数据（无论通过哪种方式启动应用都会执行）
try:
    create_initial_data()
except Exception as e:
    print(f'初始化数据时出错：{e}')


# 在应用直接运行时启动服务器
if __name__ == '__main__':
    app.run()
