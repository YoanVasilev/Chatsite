from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user, user_logged_in, user_logged_out
from flask_socketio import SocketIO, send, emit, join_room, leave_room, Namespace
from flask_session import Session
import random
from string import ascii_uppercase 
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
#app.config['SECRET_KEY'] = 'gosho'
app.secret_key = 'parola'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db
socketio = SocketIO(app)
Session(app)

online_users = set() ## later
session_sids = {}
rooms = {}

login_manager = LoginManager()
login_manager.init_app(app)

##@user_logged_in.connect
##def handle_user_logged_in(sender, user, **kwargs):  saving this for later in order to see if a user is online or not
##    online_users.add(user.id)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean(), default=False)

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
    
    if request.method == "POST":
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
        if join != False:
            session["room"] = room
            session ["name"] = name
            return redirect(url_for("room", room=room))


    return render_template("index.html")

@app.route("/<username>", methods=["POST", "GET"])
@login_required
def foo(username):
    if request.method == "POST":
            code = request.form.get("code")
            join = request.form.get("join", False)
            create = request.form.get("create", False)

            if join != False or create != False:

                if join != False and not code:
                    return render_template("index.html", error="Please enter a room code.")

                room = code
                if create != False:
                    room = generate_code(4)
                    rooms[room] = {"members" : 0, "messages": []}
                    session["room"] = room
                    session ["name"] = username
                    return redirect(url_for("room", room=room))

                if join != False and code not in rooms:
                    return render_template("index.html", error="Room does not exist", code=code)

                session["room"] = room
                session ["name"] = username
                return redirect(url_for("room", room=room))


    return render_template("main.html")



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
            return redirect("/{}".format(user.username))
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
        chat_rooms = ChatRoom.query.all()
        for roomchat in chat_rooms:
            rooms[roomchat.name] = {'members' : 'private', 'messages' : []}

        if room is None or current_user.username is None or room not in rooms:
            print("code goes to redirect index")
            return redirect(url_for("index"))
        print("code is going to execute roomhtml messages")
        return render_template("room.html", code=room, messages=rooms[room]["messages"])
    else:
        room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        render_template("index.html", error="something went wrong")

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("invite")
def invite_onsend(data):
    recipient_username = data['username']
    recipient = User.query.filter_by(username=recipient_username).first()
    recipient_sid = session_sids.get(recipient.id)
    if recipient_sid:
        sender_username = current_user.username
        if not sender_username:
            return render_template("main.html", error="sender_username didnt get value from current_user")
        
        message = f'{sender_username} is inviting you to chat'
        emit('receive_invite', {"message" : message, "sender_username" : sender_username}, room=recipient_sid)
    else:
        print("recipient is not online")
        render_template("main.html", error="Recipient is not online")

@socketio.on("begin_privatechat")
@login_required
def begin_chat(data):

    if data['sender_or_reciever'] == 'reciever':
        sender = User.query.filter_by(username=data['sender_username']).first()
        recipient = User.query.filter_by(username=current_user.username).first()

        if not ChatRoom.query.filter_by(user1_id=sender.id, user2_id=recipient.id).first():
            room = generate_code(5)
            new_chatroom = ChatRoom(name=room, user1_id=sender.id, user2_id=recipient.id)
            db.session.add(new_chatroom)
            db.session.commit()
            session["room"] = room
            session["name"] = recipient.username
            socketio.emit('recipient_accept_invite', {"room" : room}, room=session_sids.get(sender.id))
            return redirect(url_for("room", room=room))
        else:
            room = ChatRoom.query.filter_by(user1_id=sender.id, user2_id=recipient.id).first()
            session["room"] = room.name
            session["name"] = current_user.username
            
            join_room(room.name)
            # Emit a 'redirect' event to the client 
            url = url_for("room", room=room.name)
            socketio.emit('recipient_accept_invite', {"room" : room.name}, room=session_sids.get(sender.id))
            socketio.emit('redirect', {'url' : url}, room = request.sid)
            return redirect(url_for("room", room=room.name))

    #elif data['sender_or_reciever'] == 'sender':
    #    session["room"] = data['room']
    #    session["name"] = current_user.username
    #    join_room(data['room'])
    #    url = url_for("room", room=data['room'])
    #    socketio.emit('redirect', {'url' : url}, room = request.sid)
    #    return redirect(url_for("room", room=data['room']))


@socketio.on("message")
def message(data):
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
    if not current_user.is_authenticated:
        room = session.get("room")
        name = session.get("name")
        if not room or not name:
            return
        if room not in rooms:
            leave_room(room)
            return

        join_room(room)
        send({"name": name, "message" : "has entered the room"}, to=room)
        rooms[room]["members"] += 1
        print(f"{name} joined room {room}")

    else:
        room = session.get("room")
        name = session.get("name")
        join_room(room)
        session_sids[current_user.id] = request.sid
        print("code went here!!!!!!!!")
        message = {'message': 'Connected'}
        socketio.emit(message, to=session_sids[current_user.id])



@socketio.on("disconnect")
def disconnect():
   ## if not current_user.is_authenticated:
        room = session.get("room")
        name = session.get("name")
        print("ENTERING DISCONNECT ON!!!!!!!!!!!!!!!!!!!!!!!!")
        if room in rooms:
            rooms[room]["members"] -= 1
            if rooms[room]["members"] <= 0:
                del rooms[room]
        send({"name": name, "message" : "has left the room"}, to=room)
        print(f"{name} has left room {room}")
        if not current_user.is_authenticated:
            logout_user
        print("user logged out")
   ## else:
    




if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="localhost", debug=False) 