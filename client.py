import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Canvas, Scrollbar
import socket
import threading
import json
import os

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5555
BUFFER_SIZE = 1024
DOWNLOAD_PATH = "client_downloads"

class ChatClientGUI:
    def __init__(self, master):
        self.master = master
        master.title("Modern Chat Application")

        # --- Styling ---
        self.style = ttk.Style()
        self.style.theme_use('clam')  # 'clam', 'alt', 'default', 'classic', 'vista', 'xpamare'

        # Base style for labels, entries, buttons
        self.style.configure("TLabel", padding=8, font=('Helvetica', 10))
        self.style.configure("TEntry", padding=8, font=('Helvetica', 10))
        self.style.configure("TButton", padding=8, font=('Helvetica', 10), relief="flat", background="#007BFF", foreground="white")
        self.style.map("TButton", background=[('active', '#0056b3')]) # Darker blue on hover

        # Style for message bubbles (frames)
        self.style.configure("UserMessage.TFrame", background="#DCF8C6", padding=10, borderwidth=1, relief="solid") # Greenish for user messages
        self.style.configure("OtherMessage.TFrame", background="#F0F0F0", padding=10, borderwidth=1, relief="solid") # Light gray for other messages

        # --- Variables ---
        self.username = tk.StringVar()
        self.message = tk.StringVar()
        self.client_socket = None
        self.receive_thread = None

        if not os.path.exists(DOWNLOAD_PATH):
            os.makedirs(DOWNLOAD_PATH)

        # --- UI Elements ---
        frame_username = ttk.Frame(master, padding=10)
        frame_username.pack(pady=10, fill=tk.X)
        ttk.Label(frame_username, text="Username:").pack(side=tk.LEFT)
        self.username_entry = ttk.Entry(frame_username, textvariable=self.username)
        self.username_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        self.connect_button = ttk.Button(frame_username, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(side=tk.LEFT)
        self.disconnect_button = ttk.Button(frame_username, text="Disconnect", command=self.disconnect_server, state=tk.DISABLED)
        self.disconnect_button.pack(side=tk.LEFT, padx=5)

        # Chat Log Area (using Canvas and Frame for scrollable messages)
        self.chat_canvas = Canvas(master, bd=0, highlightthickness=0)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.scrollbar = Scrollbar(master, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_frame = ttk.Frame(self.chat_canvas, padding=10) # Frame inside canvas to hold messages
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.chat_canvas.bind('<Configure>', lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor=tk.NW, tags="chat_frame_tag") # Tag for easy reference
        self.chat_frame.bind("<Configure>", self.on_frame_configure)

        self.message_frames = [] # Store message frames to manage scrolling

        frame_message = ttk.Frame(master, padding=10)
        frame_message.pack(pady=10, fill=tk.X)
        self.message_entry = ttk.Entry(frame_message, textvariable=self.message)
        self.message_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        self.send_button = ttk.Button(frame_message, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.LEFT)
        self.file_button = ttk.Button(frame_message, text="Send File", command=self.open_file_dialog, state=tk.DISABLED)
        self.file_button.pack(side=tk.LEFT, padx=5)


        # --- Bindings ---
        self.connect_button.bind("<Return>", lambda event=None: self.connect_to_server())
        self.send_button.bind("<Return>", lambda event=None: self.send_message())


    def connect_to_server(self):
        username = self.username.get().strip()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty!")
            return

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((SERVER_HOST, SERVER_PORT))
            self.client_socket.send(username.encode('utf-8'))
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            self.connect_button['state'] = tk.DISABLED
            self.disconnect_button['state'] = tk.NORMAL
            self.file_button['state'] = tk.NORMAL
            self.username_entry['state'] = tk.DISABLED
            self.log_message("System", "Connected to server!") # Use "System" for system messages

        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.client_socket = None
            self.connect_button['state'] = tk.NORMAL # Re-enable connect button on failure


    def disconnect_server(self):
        if self.client_socket:
            try:
                self.client_socket.close()
                self.client_socket = None
                self.receive_thread = None
                self.connect_button['state'] = tk.NORMAL
                self.disconnect_button['state'] = tk.DISABLED
                self.file_button['state'] = tk.DISABLED
                self.username_entry['state'] = tk.NORMAL
                self.log_message("System", "Disconnected from server.")
            except Exception as e:
                messagebox.showerror("Disconnection Error", f"Error disconnecting: {e}")


    def receive_messages(self):
        while self.client_socket:
            try:
                message = self.client_socket.recv(BUFFER_SIZE).decode('utf-8')
                if not message:
                    self.log_message("System", "Server disconnected.")
                    self.disconnect_server()
                    break
                try:
                    message_data = json.loads(message)
                    message_type = message_data.get('type')

                    if message_type == 'message':
                        username = message_data.get('username')
                        content = message_data.get('content')
                        self.log_message(username, content)
                    elif message_type == 'file_transfer':
                        filename = message_data.get('filename')
                        file_data_str = message_data.get('data')
                        file_data_bytes = file_data_str.encode('latin-1', errors='ignore')
                        filepath = os.path.join(DOWNLOAD_PATH, filename)
                        with open(filepath, 'wb') as f:
                            f.write(file_data_bytes)
                        self.log_message("System", f"Received file: {filename} saved to '{DOWNLOAD_PATH}'")
                    elif message_type == 'file_error':
                        error_message = message_data.get('message')
                        self.log_message("System", f"File error: {error_message}")
                    else:
                        self.log_message("System", f"Unknown message type: {message}") # Handle unknown types

                except json.JSONDecodeError:
                    self.log_message("System", f"Received non-JSON message: {message}") # Handle non-JSON messages
            except OSError:
                if self.client_socket:
                    self.log_message("System", "Connection closed by server.")
                self.disconnect_server()
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                self.log_message("System", f"Error receiving message: {e}")
                self.disconnect_server()
                break


    def send_message(self):
        message_text = self.message.get().strip()
        if message_text and self.client_socket:
            message_json = json.dumps({'type': 'message', 'content': message_text, 'username': self.username.get()}) # Include username when sending
            try:
                self.client_socket.send(message_json.encode('utf-8'))
                self.message.set("")
            except Exception as e:
                messagebox.showerror("Send Error", f"Error sending message: {e}")
                self.disconnect_server()


    def log_message(self, sender_username, text):
        """Logs messages to the chat area, creating message bubbles."""
        is_user_message = sender_username == self.username.get()
        style_name = "UserMessage.TFrame" if is_user_message else "OtherMessage.TFrame"
        alignment = tk.E if is_user_message else tk.W # Right for user, Left for others

        message_frame = ttk.Frame(self.chat_frame, style=style_name)
        message_frame.pack(pady=(5, 5), fill=tk.X, anchor=alignment, padx=10 if is_user_message else (0, 10)) # Align right/left and add padding

        username_label = ttk.Label(message_frame, text=sender_username + ":", font=('Helvetica', 10, 'bold'), background=self.style.lookup(style_name, 'background')) # Get background from style
        username_label.pack(anchor=tk.W)
        message_label = ttk.Label(message_frame, text=text, wraplength=400, justify=tk.LEFT, background=self.style.lookup(style_name, 'background')) # Wrap text
        message_label.pack(anchor=tk.W)

        self.message_frames.append(message_frame) # Keep track of frames
        self.chat_frame.update_idletasks() # Update frame to get correct scroll region
        self.chat_canvas.yview_moveto(1.0) # Scroll to bottom

    def on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame."""
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))


    def open_file_dialog(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            self.send_file(filepath)

    def send_file(self, filepath):
        if not self.client_socket:
            messagebox.showerror("Error", "Not connected to server.")
            return

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            request_data = {
                'type': 'file_upload_request',
                'filename': filename,
                'filesize': filesize,
                'username': self.username.get() # Send username with file upload request
            }
            self.client_socket.send(json.dumps(request_data).encode('utf-8'))
            self.client_socket.sendall(file_data)
            self.log_message(self.username.get(), f"Sending file: {filename} ({filesize} bytes)")

        except FileNotFoundError:
            messagebox.showerror("File Error", "File not found.")
        except Exception as e:
            messagebox.showerror("File Send Error", f"Error sending file: {e}")
            self.disconnect_server()


def main():
    root = tk.Tk()
    root.geometry("700x600") # Increased window size
    client_gui = ChatClientGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()