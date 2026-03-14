from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flashmsg-super-secret-key'

# Налаштування бази даних
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ВАЖЛИВО: Явно вказуємо gevent для Render, щоб уникнути конфліктів з eventlet
socketio = SocketIO(app, 
    cors_allowed_origins="*", 
    async_mode='gevent',
    manage_session=False
)

# Моделі бази даних
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    content = db.Column(db.Text)
    timestamp = db.Column(db.String(10))

# Створення бази при запуску
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

# Обробка входу та реєстрації
@socketio.on('login_or_register')
def handle_login(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        emit('login_error', {'msg': 'Введіть логін та пароль!'})
        return

    user = User.query.filter_by(username=username).first()
    
    if not user:
        # Реєстрація нового користувача
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        emit('login_success', {'username': username})
    else:
        # Перевірка пароля існуючого користувача
        if check_password_hash(user.password, password):
            emit('login_success', {'username': username})
        else:
            emit('login_error', {'msg': 'Невірний пароль!'})

# Обробка текстових повідомлень
@socketio.on('send_message')
def handle_message(data):
    now = datetime.now().strftime("%H:%M")
    emit('receive_message', {
        'username': data['username'], 
        'message': data['message'], 
        'time': now
    }, broadcast=True)

# Обробка зображень
@socketio.on('send_image')
def handle_image(data):
    now = datetime.now().strftime("%H:%M")
    emit('receive_message', {
        'username': data['username'], 
        'image': data['image'], 
        'time': now
    }, broadcast=True)

# Очищення чату (локально у клієнтів)
@socketio.on('clear_chat')
def handle_clear():
    emit('chat_cleared', broadcast=True)

# Друк статусу "пише..."
@socketio.on('typing')
def handle_typing(data):
    emit('display_typing', {'username': data['username']}, broadcast=True, include_self=False)

if __name__ == '__main__':
    # Для локального запуску, Render використовує Gunicorn
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
