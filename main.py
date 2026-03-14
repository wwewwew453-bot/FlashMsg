import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashmsg.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- МОДЕЛІ ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending' або 'accepted'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

# --- ЛОГІКА ДРУЗІВ ---

@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    if user_id == current_user.id:
        return redirect(url_for('index'))
    
    # Перевірка на існуючий запит
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
        flash("Запит прийнято!")
    return redirect(url_for('index'))

@app.route('/reject_friend/<int:req_id>')
@login_required
def reject_friend(req_id):
    req = Friendship.query.get_or_404(req_id)
    if req.receiver_id == current_user.id or req.sender_id == current_user.id:
        db.session.delete(req)
        db.session.commit()
        flash("Запит видалено")
    return redirect(url_for('index'))

# --- ОСНОВНІ МАРШРУТИ ---

@app.route('/')
@login_required
def index():
    # Отримуємо всіх користувачів для пошуку (крім себе)
    all_users = User.query.filter(User.id != current_user.id).all()
    
    # Отримуємо підтверджених друзів
    friends = Friendship.query.filter(
        ((Friendship.sender_id == current_user.id) | (Friendship.receiver_id == current_user.id)) & 
        (Friendship.status == 'accepted')
    ).all()

    # Отримуємо вхідні запити
    pending_requests = Friendship.query.filter_by(receiver_id=current_user.id, status='pending').all()
    
    return render_template('intel.html', all_users=all_users, friends=friends, requests=pending_requests)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Створює таблицю Friendship, якщо її немає
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
