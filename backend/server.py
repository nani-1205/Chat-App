from flask import Flask, render_template
from flask_sockets import Sockets
import json
import pymongo
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
sockets = Sockets(app)

clients = []  # List to hold connected WebSocket clients

# MongoDB Configuration from .env
mongo_host = os.getenv("MONGO_HOST", "localhost")
mongo_port = int(os.getenv("MONGO_PORT", "27017"))
mongo_user = os.getenv("MONGO_USER")
mongo_password = os.getenv("MONGO_PASSWORD")
mongo_auth_db = os.getenv("MONGO_AUTH_DB", "admin")

# Construct MongoDB URI
if mongo_user and mongo_password:
    mongodb_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/?authSource={mongo_auth_db}"
else:
    mongodb_uri = f"mongodb://{mongo_host}:{mongo_port}/"

db_client = pymongo.MongoClient(mongodb_uri)
db = db_client["web_chat_database"]
messages_collection = db["messages"]

# Check and create 'messages' collection if it doesn't exist (similar to before)
if "messages" not in db.list_collection_names():
    print("Creating 'messages' collection in MongoDB...")
    messages_collection = db.create_collection("messages")
    print("'messages' collection created.")
else:
    print("'messages' collection already exists.")
    messages_collection = db["messages"]


@sockets.route('/ws')  # WebSocket endpoint at /ws
def echo_socket(ws):
    clients.append(ws)  # Add new client to the list
    print(f"Client connected: {ws}")

    try:
        while not ws.closed:
            message = ws.receive()  # Receive message from client
            if message:
                print(f"Received message: {message}")
                message_data = json.loads(message) # Expecting JSON messages
                message_type = message_data.get('type')

                if message_type == 'message':
                    username = message_data.get('username')
                    content = message_data.get('content')
                    timestamp = datetime.now()

                    # Store message in MongoDB
                    message_doc = {
                        "username": username,
                        "message": content,
                        "timestamp": timestamp
                    }
                    messages_collection.insert_one(message_doc)

                    # Broadcast message to all connected clients
                    formatted_message = json.dumps({
                        'type': 'message',
                        'username': username,
                        'content': content,
                        'timestamp': str(timestamp) # Serialize datetime for JSON
                    })
                    for client in clients:
                        client.send(formatted_message)

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        clients.remove(ws)  # Remove client when connection closes
        print(f"Client disconnected: {ws}")


@app.route('/')
def index():
    return render_template('index.html') # We'll create this HTML file later in frontend


if __name__ == "__main__":
    print("Starting Flask WebSocket server...")
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    server.serve_forever()