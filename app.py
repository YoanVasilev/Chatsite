from flask import Flask, render_template, request, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import random
from string import ascii_uppercase 
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = "gosho"
socketio = SocketIO(app)
app.config['DATABASE'] = 'database.db'

login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

rooms = {}

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
        
        session["room"] = room
        session ["name"] = name
        return redirect(url_for("room"))

    return render_template("index.html")

@app.route("/<username>", methods=["POST", "GET"])
@login_required
def foo(username):
    if request.method == "POST":
            code = request.form.get("code")
            join = request.form.get("join", False)
            create = request.form.get("create", False)
            
            if join != False and not code:
                return render_template("index.html", error="Please enter a room code.", code=code)

            room = code
            if create != False:
                room = generate_code(4)
                rooms[room] = {"members" : 0, "messages": []}
            elif code not in rooms:
                return render_template("index.html", error="Room does not exist", code=code)
            
            session["room"] = room
            session ["name"] = username
            return redirect(url_for("room"))

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

        conn = sqlite3.connect('database.db')


        # Query database for username
        rows = conn.execute("SELECT * FROM users WHERE username = ?", (request.form.get("username"),))
        user = rows.fetchall()
        # Ensure username exists and password is correct
        if len(user) != 1 or not check_password_hash(user[0][2], request.form.get("password")):
            return render_template("login.html", error="Wrong username or password.")
        conn.commit()
        conn.close()
        # save user information in session
        session["username"] = user[0][1]
        session["user_id"] = user[0][0]
        user_id = user[0][0]
        user = User(user_id)
        login_user(user)

        # Redirect user to home page
        return redirect("/{}".format(session["username"]))

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
        conn = sqlite3.connect('database.db')
        

        # Ensure username is free
        name_check = conn.execute("SELECT username FROM users WHERE username= ?", (request.form.get("username"),))
        if name_check.fetchall():
            return render_template("register.html", error="Username already taken.")

        # Insert the new user into users
        user_name = request.form.get("username")
        hash_pass = generate_password_hash(request.form.get("password"))

        conn.execute("INSERT INTO users (username, hash) VALUES(?, ?)", (user_name, hash_pass))
        conn.commit()
        conn.close()
        return redirect("/login")
    
    return render_template("register.html")

@app.route("/private", methods=["POST", "GET"])
def private():
    if request.method == "POST":
        username = current_user.username
        recipient_username = request.form.get("username")
        message = request.form.get("msg")
        current_time = datetime.now()

        conn = sqlite3.connect('database.db')

        conn.execute("INSERT INTO private_chats (username1, username2, messages, date) VALUES(?, ?, ?, ?)", (username, recipient_username, message, current_time))

        ## conn.commit()
        conn.close()
        room = generate_code(5)
        rooms[room] = {"members" : 0, "messages": []}
        session["room"] = room
        session ["name"] = username ## nameri kak da slojish idto na usera v private.html i da mi pratish invite koito da go redirectva v chat staqta
        return redirect(url_for("room"))



@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("index"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("invite")
def invite_onsend(data):
    recipient_username = data["username"]  # working on it


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

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message" : "has left the room"}, to=room)
    print(f"{name} has left room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True) 