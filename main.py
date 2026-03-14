from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flashmsg-super-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# Налаштування для стабільної роботи в хмарі
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    content = db.Column(db.Text)
    timestamp = db.Column(db.String(10))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('login_or_register')
def handle_login(data):
    user = User.query.filter_by(username=data['username']).first()
    if not user:
        hashed_pw = generate_password_hash(data['password'])
        new_user = User(username=data['username'], password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        emit('login_success', {'username': data['username']})
    else:
        if check_password_hash(user.password, data['password']):
            emit('login_success', {'username': data['username']})
        else:
            emit('login_error', {'msg': 'Невірний пароль!'})

@socketio.on('send_message')
def handle_message(data):
    now = datetime.now().strftime("%H:%M")
    emit('receive_message', {'username': data['username'], 'message': data['message'], 'time': now}, broadcast=True)

@socketio.on('send_image')
def handle_image(data):
    now = datetime.now().strftime("%H:%M")
    emit('receive_message', {'username': data['username'], 'image': data['image'], 'time': now}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
