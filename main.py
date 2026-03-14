import os
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, and_

app = Flask(__name__)
app.config['SECRET_KEY'] = '1234'
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
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_reqs')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_reqs')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
@login_required
def index():
    all_users = User.query.filter(User.id != current_user.id).all()
    # Тільки підтверджені друзі
    friendships = Friendship.query.filter(
        or_(
            and_(Friendship.sender_id == current_user.id, Friendship.status == 'accepted'),
            and_(Friendship.receiver_id == current_user.id, Friendship.status == 'accepted')
        )
    ).all()
    
    friends = [f.receiver if f.sender_id == current_user.id else f.sender for f in friendships]
    requests = Friendship.query.filter_by(receiver_id=current_user.id, status='pending').all()
    return render_template('index.html', all_users=all_users, friends=friends, requests=requests)

@app.route('/chat/<int:friend_id>')
@login_required
def chat(friend_id):
    friend = User.query.get_or_404(friend_id)
    history = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == friend_id),
            and_(Message.sender_id == friend_id, Message.recipient_id == current_user.id)
        )
    ).all()
    return render_template('chat.html', friend=friend, history=history)

@app.route('/add_friend/<int:user_id>')
@login_required
def add_friend(user_id):
    exists = Friendship.query.filter(or_(
        and_(Friendship.sender_id == current_user.id, Friendship.receiver_id == user_id),
        and_(Friendship.sender_id == user_id, Friendship.receiver_id == current_user.id)
    )).first()
    if not exists:
        db.session.add(Friendship(sender_id=current_user.id, receiver_id=user_id))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/accept_friend/<int:req_id>')
@login_required
def accept_friend(req_id):
    req = Friendship.query.get(req_id)
    if req and req.receiver_id == current_user.id:
        req.status = 'accepted'
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'))
        if not User.query.filter_by(username=request.form.get('username')).first():
            db.session.add(User(username=request.form.get('username'), password=hashed_pw))
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@socketio.on('private_message')
def handle_private_message(data):
    recipient_id = data['recipient_id']
    content = data['message']
    new_msg = Message(sender_id=current_user.id, recipient_id=recipient_id, content=content)
    db.session.add(new_msg)
    db.session.commit()
    
    room = f"room_{min(current_user.id, recipient_id)}_{max(current_user.id, recipient_id)}"
    emit('new_message', {'sender': current_user.username, 'msg': content}, room=room)

@socketio.on('join')
def on_join(data):
    friend_id = data['friend_id']
    room = f"room_{min(current_user.id, friend_id)}_{max(current_user.id, friend_id)}"
    join_room(room)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port)
