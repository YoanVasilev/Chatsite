from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import random
from string import ascii_uppercase 

app = Flask(__name__)
app.config['SECRET_KEY'] = "gosho"
socketio = SocketIO(app)

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
            return render_template("home.html", error="Room does not exist", code=code, name=name)

    return render_template("index.html")

if __name__ == "__main__":
    socketio.run(app, debug=True) 