import socket
import threading
import json
import pymongo
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5555
BUFFER_SIZE = 1024
FILE_STORAGE_PATH = "server_files"

class ChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.usernames = {}

        mongo_host = os.getenv("MONGO_HOST", "localhost") # Default to localhost if not set
        mongo_port = int(os.getenv("MONGO_PORT", "27017")) # Default to 27017 if not set
        mongo_user = os.getenv("MONGO_USER") # Can be None if no auth
        mongo_password = os.getenv("MONGO_PASSWORD") # Can be None if no auth
        mongo_auth_db = os.getenv("MONGO_AUTH_DB", "admin") # Default to 'admin' if auth is used

        # Construct MongoDB URI based on authentication details
        if mongo_user and mongo_password:
            mongodb_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/?authSource={mongo_auth_db}"
        else:
            mongodb_uri = f"mongodb://{mongo_host}:{mongo_port}/"


        self.db_client = pymongo.MongoClient(mongodb_uri) # MongoDB Client - Authentication handled by URI
        self.db = self.db_client["chat_database"] # Access the database - DB will be created if not exists on first write.

        # Check if the 'messages' collection exists, create if not
        if "messages" not in self.db.list_collection_names():
            print("Creating 'messages' collection in MongoDB...")
            self.messages_collection = self.db.create_collection("messages")
            print("'messages' collection created.")
        else:
            print("'messages' collection already exists.")
            self.messages_collection = self.db["messages"]


        if not os.path.exists(FILE_STORAGE_PATH):
            os.makedirs(FILE_STORAGE_PATH)

    def start(self):
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen()
            print(f"Server listening on {self.host}:{self.port}")

            while True:
                client_socket, client_address = self.server_socket.accept()
                print(f"Accepted connection from {client_address}")

                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.server_socket.close()
            self.db_client.close()

    def broadcast(self, message, sender_socket=None):
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.send(message.encode('utf-8'))
                except:
                    self.remove_client(client)

    def store_message_in_db(self, username, message_text, file_info=None):
        message_data = {
            "username": username,
            "message": message_text,
            "timestamp": datetime.now(),
            "file_info": file_info
        }
        self.messages_collection.insert_one(message_data)

    def handle_client(self, client_socket):
        self.clients.append(client_socket)
        username = None

        try:
            username_bytes = client_socket.recv(BUFFER_SIZE)
            if not username_bytes:
                self.remove_client(client_socket)
                return
            username = username_bytes.decode('utf-8')
            self.usernames[client_socket] = username
            print(f"Client username set to: {username}")
            self.broadcast(json.dumps({'type': 'message', 'content': f"{username} has joined the chat!", 'username': 'System'}), client_socket)

            while True:
                message_data_bytes = client_socket.recv(BUFFER_SIZE)
                if not message_data_bytes:
                    break

                message_data_str = message_data_bytes.decode('utf-8')
                try:
                    message_data = json.loads(message_data_str)
                    message_type = message_data.get('type')

                    if message_type == 'message':
                        message_text = message_data.get('content')
                        message_username = message_data.get('username')
                        print(f"Received message from {message_username}: {message_text}")
                        self.store_message_in_db(message_username, message_text)
                        formatted_message = json.dumps({'type': 'message', 'content': message_text, 'username': message_username})
                        self.broadcast(formatted_message, client_socket)

                    elif message_type == 'file_request':
                        filename = message_data.get('filename')
                        filepath = os.path.join(FILE_STORAGE_PATH, filename)
                        if os.path.exists(filepath):
                            with open(filepath, 'rb') as f:
                                file_data = f.read()
                            response = {'type': 'file_transfer', 'filename': filename, 'data': file_data.decode('latin-1', errors='ignore')}
                            client_socket.send(json.dumps(response).encode('utf-8'))
                        else:
                            error_response = {'type': 'file_error', 'message': 'File not found on server.'}
                            client_socket.send(json.dumps(error_response).encode('utf-8'))

                    elif message_type == 'file_upload_request':
                        filename = message_data.get('filename')
                        filesize = message_data.get('filesize')
                        uploading_username = message_data.get('username')
                        print(f"Receiving file '{filename}' ({filesize} bytes) from {uploading_username}")
                        file_content_bytes = b''
                        bytes_received = 0
                        while bytes_received < filesize:
                            chunk = client_socket.recv(BUFFER_SIZE)
                            if not chunk:
                                break
                            file_content_bytes += chunk
                            bytes_received += len(chunk)

                        if bytes_received == filesize:
                            filepath = os.path.join(FILE_STORAGE_PATH, filename)
                            with open(filepath, 'wb') as f:
                                f.write(file_content_bytes)
                            print(f"File '{filename}' saved successfully.")
                            file_info = {'filename': filename, 'size': filesize}
                            self.store_message_in_db(uploading_username, f"File uploaded: {filename}", file_info)
                            broadcast_message = json.dumps({'type': 'message', 'content': f"{uploading_username} uploaded file: {filename}", 'username': 'System'})
                            self.broadcast(broadcast_message, client_socket)
                        else:
                            print(f"File '{filename}' upload incomplete.")
                            error_message = f"File upload for '{filename}' was incomplete."
                            client_socket.send(json.dumps({'type': 'error', 'message': error_message}).encode('utf-8'))

                except json.JSONDecodeError:
                    print(f"Received invalid JSON from {username}")
                except Exception as e:
                    print(f"Error handling client {username}: {e}")
                    break

        except Exception as e:
            print(f"Error in client connection with {username}: {e}")
        finally:
            self.remove_client(client_socket)
            if username:
                self.broadcast(json.dumps({'type': 'message', 'content': f"{username} has left the chat!", 'username': 'System'}), client_socket)


    def remove_client(self, client_socket):
        if client_socket in self.clients:
            username_to_remove = self.usernames.get(client_socket, "Unknown")
            print(f"Removing client: {username_to_remove}")
            self.clients.remove(client_socket)
            if client_socket in self.usernames:
                del self.usernames[client_socket]
            client_socket.close()


if __name__ == "__main__":
    server = ChatServer(SERVER_HOST, SERVER_PORT)
    server.start()