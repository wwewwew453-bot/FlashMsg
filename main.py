import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flash-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashmsg.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- МОДЕЛІ БАЗИ ДАНИХ ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # 'pending' або 'accepted'
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

# --- ЛОГІКА ДЛЯ ДРУЗІВ ---

@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    if user_id != current_user.id:
        exists = Friendship.query.filter(
            ((Friendship.sender_id == current_user.id) & (Friendship.receiver_id == user_id)) |
            ((Friendship.sender_id == user_id) & (Friendship.receiver_id == current_user.id))
        ).first()
        if not exists:
            new_req = Friendship(sender_id=current_user.id, receiver_id=user_id)
            db.session.add(new_req)
            db.session.commit()
            flash("Запит надіслано!")
    return redirect(url_for('index'))

@app.route('/accept_friend/<int:req_id>')
@login_required
def accept_friend(req_id):
    req = Friendship.query.get_or_404(req_id)
    if req.receiver_id == current_user.id:
        req.status = 'accepted'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/reject_friend/<int:req_id>')
@login_required
def reject_friend(req_id):
    req = Friendship.query.get_or_404(req_id)
    if req.receiver_id == current_user.id or req.sender_id == current_user.id:
        db.session.delete(req)
        db.session.commit()
    return redirect(url_for('index'))

# --- ОСНОВНІ МАРШРУТИ ---

@app.route('/')
@login_required
def index():
    all_users = User.query.filter(User.id != current_user.id).all()
    # Отримуємо об'єкти друзів
    friends_list = Friendship.query.filter(
        ((Friendship.sender_id == current_user.id) | (Friendship.receiver_id == current_user.id)) & 
        (Friendship.status == 'accepted')
    ).all()
    pending = Friendship.query.filter_by(receiver_id=current_user.id, status='pending').all()
    return render_template('intel.html', all_users=all_users, friends=friends_list, requests=pending)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- SOCKET.IO ---
@socketio.on('message')
def handle_message(data):
    emit('message', data, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
