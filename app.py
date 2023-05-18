from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, user_logged_in, user_logged_out
from flask_socketio import SocketIO, send, emit, join_room, leave_room, Namespace, disconnect
from flask_session import Session
import random
from string import ascii_uppercase 
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
#app.config['SECRET_KEY'] = 'gosho'
app.config['SECRET_KEY'] = 'parola'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db
socketio = SocketIO(app, manage_session=True)
Session(app)

online_users = set() ## later
session_sids = {}
rooms = {}

login_manager = LoginManager()
login_manager.init_app(app)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean(), default=False)
    chatroom_id = db.Column(db.Integer, db.ForeignKey('chatroom.id'))

    chatroom = db.relationship('ChatRoom', backref='users', foreign_keys=[chatroom_id])

class ChatRoom(db.Model):
    __tablename__ = 'chatroom'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # define the relationship with ChatMessage
    messages = db.relationship('ChatMessage', backref='chat_room', lazy=True)

class ChatMessage(db.Model):
    __tablename__ = 'chatmessage'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(300), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('chatroom.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break
    return code

@app.route("/", methods=["POST", "GET"])
def index():

    if request.method == ("POST"):

        if current_user.is_authenticated:
            name = current_user.username
            code = request.form.get("code")
            join = request.form.get("join", False)
            create = request.form.get("create", False)

            if join != False and not code:
                return render_template("index.html", error="Please enter a room code.", code=code, name=name)
        
            room = code
            if create != False:
                room = generate_code(4)
                rooms[room] = {"members": 0, "messages": []}
            elif code not in rooms:
                return render_template("index.html", error="Room does not exist.", code=code, name=name)
        
            session["room"] = room
            session["name"] = name
            return redirect(url_for("room", room=room))

        else:

                name = request.form.get("name")
                code = request.form.get("code")
                join = request.form.get("join", False)
                create = request.form.get("create", False)

                if not name:
                    return render_template("index.html", error="Please enter a name.", code=code, name=name)

                if join != False and not code:
                    return render_template("index.html", error="Please enter a room code.", code=code, name=name)

                room = code
                if create != False:
                    room = generate_code(4)
                    rooms[room] = {"members" : 0, "messages": []}
                elif code not in rooms:
                    return render_template("index.html", error="Room does not exist", code=code, name=name)
                
                session["room"] = room
                session ["name"] = name
                return redirect(url_for("room", room=room))


    return render_template("index.html", current=current_user)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("login.html", error="Place enter a username.")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("login.html", error="Place enter a password.")

        user_name = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=user_name).first()
        print(user)
        if user is not None and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect("/")
        else:
            return render_template("login.html", error="wrong username or password")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/register", methods=["POST", "GET"])
def register():
    session.clear()

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("register.html", error="Place enter a username.")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("register.html", error="Pleace enter a password.")

        # Ensure confirm password was submitted
        elif not request.form.get("confirmation"):
            return render_template("register.html", error="Pleace submit a confirmation password")

        # Ensure passwords are the same
        if request.form.get("password") != request.form.get("confirmation"):
            return render_template("register.html", error="Passwords do not match.")
        
        # connection to the database
        user_name = request.form.get("username")
        hash_pass = generate_password_hash(request.form.get("password"))
        

        # Ensure username is free
        name_check = User.query.filter_by(username = user_name).first()
        if name_check:
            return render_template("register.html", error="Username already taken.")

        user = User(username=user_name, password_hash=hash_pass, is_active=True)
        db.session.add(user)
        db.session.commit()
        return redirect("/login")
    
    return render_template("register.html")

@app.route("/room/<room>")
def room(room):

    if current_user.is_authenticated: 
        if current_user.chatroom_id is None:
            room = room
            if room not in rooms:
                print('user is in a public room that doesnt exist')
                return redirect(url_for('index'))
            return render_template("room.html", room=room, sent_messages=rooms[room]["messages"])
        if current_user.chatroom_id is not None:
            room_from_id = ChatRoom.query.filter_by(id=current_user.chatroom_id).first()
            if room_from_id.name != room:
                print("user has chatroom_id but its not the one expected (most likely didnt clear on disconnect)")
                current_user.chatroom_id = None
                db.session.commit()
                return redirect(url_for("index"))
        
        chatroom = ChatRoom.query.filter_by(name=room).first()
        room_messages = db.session.query(ChatMessage.content, User.username).join(User, ChatMessage.sender_id == User.id)\
        .filter(ChatMessage.room_id == chatroom.id).order_by(ChatMessage.timestamp).all()
        room_from_id = ChatRoom.query.filter_by(id=current_user.chatroom_id).first()
        friend = None
        if room_from_id.user1_id == current_user.id:
            friend = User.query.filter_by(id=room_from_id.user2_id).first()
        else:
            friend = User.query.filter_by(id=room_from_id.user1_id).first()

        return render_template("room.html", room_messages=room_messages, current=current_user, friend = friend.username, user_room = room_from_id.name, room=room)
    
    else:
        if room not in rooms:
                print('user is in a public room that doesnt exist')
                return redirect(url_for('index'))
        room = session['room']
        if room is None or session.get("name") is None or room not in rooms:
            render_template("index.html", error="something went wrong")

        return render_template("room.html", room=room, sent_messages=rooms[room]["messages"])

@socketio.on("invite")
def handle_invite(data): # this code is intended to run by the sender
    if data['recipient'] is None : render_template("index.html", error="Server didnt get recipient name data")
    recipient_username = data['recipient']
    sender = User.query.filter_by(username=current_user.username).first()
    recipient = User.query.filter_by(username=recipient_username).first()
    if recipient is not None:
        chatroom = ChatRoom.query.filter_by(user1_id=sender.id, user2_id=recipient.id).first()
        if chatroom is None:
            chatroom = ChatRoom.query.filter_by(user1_id=recipient.id, user2_id=sender.id).first()
        if chatroom is None:
            room = generate_code(5)
            new_chatroom = ChatRoom(name=room, user1_id=sender.id, user2_id=recipient.id)
            db.session.add(new_chatroom)
            db.session.commit()
            sender.chatroom_id = new_chatroom.id
            recipient.chatroom_id = new_chatroom.id
            db.session.commit()
            session['name'] = sender.username
            join_room(new_chatroom.name)
            session['room'] = new_chatroom.name
            socketio.emit('accept_invite', {'room_name': new_chatroom.name}, room=recipient.username)
            socketio.emit('redirect_to_chat', {'room_name': new_chatroom.name}, room=sender.username)
            return

        sender.chatroom_id = chatroom.id
        recipient.chatroom_id = chatroom.id
        db.session.commit()
        session['name'] = sender.username
        session['room'] = chatroom.name
        join_room(chatroom.name)
        socketio.emit('accept_invite', {'room_name': chatroom.name}, room=session_sids[recipient.id])
        socketio.emit('redirect_to_chat', {'room_name': chatroom.name}, room=session_sids[sender.id])
        
    else:
        print("recipient is not online")
        render_template("index.html", error="Recipient is not online")

@socketio.on("accept_invite")
def handle_accept_invite(data):

    join_room(data['room_name'])
    socketio.emit('redirect_to_chat', {'room_name': data['room_name']}, room=session_sids[current_user.id])
    return


@socketio.on("message")
def message(data):
    if current_user.is_authenticated and data['private_or_public'] == 'private':
        room = ChatRoom.query.filter_by(id=current_user.chatroom_id).first()
        new_message = ChatMessage(content=data["data"], sender_id=current_user.id, room_id=current_user.chatroom_id)
        db.session.add(new_message)
        db.session.commit()
        print(f"{current_user.username} said: {data['data']}")

        content = {
            "name" : current_user.username,
            "message": data["data"]
        }
        send(content, to=room.name)
    else:
        room = session.get("room")
        if room not in rooms:
            return

        content = {
            "name" : session.get("name"),
            "message": data["data"]
        }
        send(content, to=room)
        rooms[room]["messages"].append(content)
        print(f"{session.get('name')} said: {data['data']}")


@socketio.on("connect")
def connect(auth):
    print("we have a connection!!!!!!!!!!!!")
    if current_user.is_authenticated and len((request.referrer).split("/")[-1]) == 5: 
        session_sids[current_user.id] = request.sid
        #if session['room'] == (request.referrer).split("/")[-1]:
        location_chatroom = ChatRoom.query.filter_by(name=(request.referrer).split("/")[-1]).first()
        if current_user.chatroom_id is None or current_user.chatroom_id != location_chatroom.id:
            if location_chatroom.user1_id != current_user.id or location_chatroom.user2_id != current_user.id:
                print(f"{current_user.username} shouldnt be in this room {location_chatroom.name}")
                return render_template("index.html", error="You are not from this chatroom so you got kicked")
            else:
                current_user.chatroom_id = location_chatroom.id
                print("current_user.chatroom_id was none or different so gave it back")
        join_room(location_chatroom.name)
        print(f"{current_user.username} connected to a private chat room")
        send({"name": current_user.username, "message" : "has entered the room"}, to=location_chatroom.name)
        

    else:
        if current_user.is_authenticated:
            session_sids[current_user.id] = request.sid
            print(f"{current_user.username} connected")

        room = session.get("room")
        name = session.get("name")
        if not room or not name:
            return
        if room not in rooms:
            leave_room(room)
            return

        join_room(room)
        send({"name": name, "message" : "has entered the room"}, to=room)
        print(f"the name of the room is {(request.referrer).split('/')[-1]} and its length is {len((request.referrer).split('/')[-1])}")
        rooms[room]["members"] += 1
        print(f"{name} joined room {room}")




@socketio.on("disconnect")
def disconnect():
    if current_user.is_authenticated and len((request.referrer).split("/")[-1]) == 5:
        print(f"{current_user.username} is disconnecting from a private chat room")
        chatroom = ChatRoom.query.filter_by(id=current_user.chatroom_id)
        leave_room(chatroom.name)
        print(f"{current_user.username} has left the private room {(request.referrer).split('/')[-1]}")
        send({"name": current_user.username, "message" : "has left the room"}, to=chatroom.name)
        current_user.chatroom_id = None
        db.session.commit()
        send({"name": current_user.username, "message" : "has left the room"}, to=chatroom.name)
        session_sids.pop(current_user.id, None)
    
    elif len((request.referrer).split("/")[-1]) == 4:
        if current_user.chatroom_id is not None:
            current_user.chatroom_id = None
            return redirect(url_for('index'))

        room = session.get("room")
        name = session.get("name")
        leave_room(room)

        if room in rooms:
            rooms[room]["members"] -= 1
            if rooms[room]["members"] <= 0:
                del rooms[room]
    
        send({"name": name, "message": "has left the room"}, to=room)
        print(f"{name} has left the public room {room}")
        if current_user.is_authenticated:
            session_sids.pop(current_user.id, None)
    


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="localhost", debug=False) 