from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import random
from string import ascii_uppercase 
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = "gosho"
socketio = SocketIO(app)

conn = sqlite3.connect('database.db')
db = conn.cursor()



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
    session.clear()
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

        # Ensure username is free
        name_check = db.execute("SELECT username FROM users WHERE username= ?", request.form.get("username"))
        if request.form.get("username") == name_check:
            return render_template("register.html", error="Username already taken.")

        # Insert the new user into users

        user_name = request.form.get("username")
        hash_pass = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", user_name, hash_pass)
        return redirect("/")


    else:
        return render_template("register.html")


@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("index"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"])

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