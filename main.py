import os
from flask import Flask, render_template, redirect, url_for, request, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = '1234'

# Налаштування бази даних
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'flashmsg.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Моделі
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Цей блок автоматично створить таблиці при першому зверненні до сайту
@app.before_request
def create_tables():
    # Виконується лише один раз
    app.before_request_funcs[None].remove(create_tables)
    db.create_all()

@app.route('/')
@login_required
def index():
    try:
        all_users = User.query.filter(User.id != current_user.id).all()
        return render_template('index.html', all_users=all_users)
    except Exception as e:
        return f"Помилка бази даних: {e}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        return "Невірний логін або пароль", 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'))
        new_user = User(username=request.form.get('username'), password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@socketio.on('message')
def handle_message(msg):
    if current_user.is_authenticated:
        emit('message', {'user': current_user.username, 'msg': msg}, broadcast=True)

if __name__ == '__main__':
    # Для локального запуску
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
