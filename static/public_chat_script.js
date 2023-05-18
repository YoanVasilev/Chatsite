document.addEventListener("DOMContentLoaded", function() { 
            // Get the input field
    var input = document.getElementById("message");

    // Execute a function when the user presses a key on the keyboard
    input.addEventListener("keypress", function(event) {
    // If the user presses the "Enter" key on the keyboard
    if (event.key === "Enter") {
        // Cancel the default action, if needed
        event.preventDefault();
        // Trigger the button element with a click
        document.getElementById("send-btn").click();
    }
    });
    var socketio = io();

    const messages = document.getElementById("messages");
    
    socketio.on("message", (data) => {
        createMessage(data.name, data.message);
    });
    
    window.sendMessage = () => {
        const message = document.getElementById("message");
        if (message.value == "") return;
        socketio.emit("message", {data: message.value, 'private_or_public' : 'public'});
        message.value = "";
    };

});