import tkinter as tk
from tkinter import messagebox, ttk
import socket
import threading
import pyaudio
from collections import deque
import time

# Audio and network settings
host = "3.66.212.112"
port = 5000

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

output_streams = {}
jitter_buffers = {}
playback_threads = {}
stop_audio_threads = False
BUFFER_FILL_THRESHOLD = 2

my_client_id = None


class VoiceChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Chat App")
        self.root.geometry("600x400")

        self.client = None
        self.username = None
        self.current_room = None
        self.is_room_owner = False

        self.setup_first_page()

    # First page: Username input
    def setup_first_page(self):
        self.clear_frame()
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(expand=True)

        tk.Label(frame, text="Welcome to Voice Chat", font=("Arial", 20, "bold")).pack(pady=10)
        tk.Label(frame, text="Enter Your Username:", font=("Arial", 14)).pack(pady=5)

        self.username_entry = tk.Entry(frame, font=("Arial", 14), width=25)
        self.username_entry.pack(pady=10)

        tk.Button(frame, text="Continue", command=self.connect_to_server, font=("Arial", 12), bg="#4CAF50", fg="white").pack(pady=20)

    # Second page: Room selection
    def setup_second_page(self):
        self.clear_frame()

        left_frame = tk.Frame(self.root, width=300, padx=10, pady=10)
        left_frame.pack(side="left", fill="y")

        right_frame = tk.Frame(self.root, padx=10, pady=10)
        right_frame.pack(side="right", expand=True, fill="both")

        tk.Label(left_frame, text="Available Rooms", font=("Arial", 14, "bold")).pack(pady=5)
        self.rooms_listbox = tk.Listbox(left_frame, font=("Arial", 12), height=15, width=30)
        self.rooms_listbox.pack(pady=5)

        tk.Button(left_frame, text="Refresh Rooms", command=self.refresh_rooms, font=("Arial", 12)).pack(pady=5)

        tk.Label(right_frame, text=f"Hello, {self.username}", font=("Arial", 14)).pack(pady=5)
        tk.Label(right_frame, text="Room Actions", font=("Arial", 12, "bold")).pack(pady=5)

        self.room_name_entry = tk.Entry(right_frame, font=("Arial", 12), width=30)
        self.room_name_entry.pack(pady=5)

        tk.Button(right_frame, text="Create Room", command=self.create_room, font=("Arial", 12), bg="#2196F3", fg="white").pack(pady=5)
        tk.Button(right_frame, text="Join Room", command=self.join_room, font=("Arial", 12), bg="#FF9800", fg="white").pack(pady=5)
        tk.Button(right_frame, text="Back", command=self.setup_first_page, font=("Arial", 12), bg="#F44336", fg="white").pack(pady=20)

        self.refresh_rooms()

    # Clear the frame for a new page
    def clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # Connect to the server
    def connect_to_server(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty!")
            return

        self.username = username

        def connect():
            try:
                self.client = socket.socket()
                self.client.settimeout(10)  # Timeout for connection
                self.client.connect((host, port))

                # First, expect the welcome message
                welcome_message = self.client.recv(4096).decode('utf-8').strip()
                print(f"Server response (Welcome): {welcome_message}")
                if "Welcome to the Voice Chat Server" not in welcome_message:
                    raise Exception(f"Unexpected server response: {welcome_message}")

                # Then, expect the client ID
                client_id_response = self.client.recv(4096).decode('utf-8').strip()
                print(f"Server response (ID): {client_id_response}")
                if not client_id_response.startswith("ID:"):
                    raise Exception(f"Invalid client ID response: {client_id_response}")

                self.handle_server_message(welcome_message)
                self.setup_second_page()

            except socket.timeout:
                messagebox.showerror("Error", "Connection timed out. Server might be unreachable.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect to server: {e}")

        threading.Thread(target=connect).start()

    # Handle server messages
    def handle_server_message(self, message):
        print(f"Server: {message}")

    # Refresh available rooms
    def refresh_rooms(self):
        # Logic to fetch available rooms from the server (mocked here)
        rooms = ["Room 1", "Room 2", "Room 3"]
        self.rooms_listbox.delete(0, tk.END)
        for room in rooms:
            self.rooms_listbox.insert(tk.END, room)

    # Create a room
    def create_room(self):
        room_name = self.room_name_entry.get().strip()
        if not room_name:
            messagebox.showerror("Error", "Room name cannot be empty!")
            return

        try:
            self.client.send(f"NEW:{room_name}".encode('utf-8'))
            response = self.client.recv(4096).decode('utf-8')
            self.handle_server_message(response)
            if "Joined room" in response:
                self.current_room = room_name
                self.start_audio_streaming()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create room: {e}")

    # Join a room
    def join_room(self):
        selected_room = self.rooms_listbox.get(tk.ACTIVE)
        if not selected_room:
            messagebox.showerror("Error", "No room selected!")
            return

        try:
            self.client.sendall(selected_room.encode('utf-8'))
            response = self.client.recv(4096).decode('utf-8')
            self.handle_server_message(response)
            if "Joined room" in response:
                self.current_room = selected_room
                self.start_audio_streaming()
            else:
                messagebox.showerror("Error", f"Failed to join room: {response}")
        except socket.timeout:
            messagebox.showerror("Error", "Request timed out. Server might not be responding.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to join room: {e}")

    # Start audio streaming
    def start_audio_streaming(self):
        threading.Thread(target=self.audio_streaming).start()

    def audio_streaming(self):
        global stop_audio_threads
        stop_audio_threads = False

        p = pyaudio.PyAudio()
        input_stream = p.open(format=Format, channels=Channels, rate=Rate, input=True, frames_per_buffer=Chunks)

        def send_audio():
            while not stop_audio_threads:
                try:
                    data = input_stream.read(Chunks, exception_on_overflow=False)
                    if data:
                        self.client.send(data)
                except:
                    break

        def receive_audio():
            global my_client_id
            f = self.client.makefile('rb')
            while not stop_audio_threads:
                try:
                    header_line = f.readline()
                    if not header_line:
                        break
                    header_line = header_line.strip()
                    if header_line.startswith(b"DATA:"):
                        parts = header_line.decode('utf-8').split(':')
                        if len(parts) == 3:
                            _, sender_id_str, length_str = parts
                            sender_id = int(sender_id_str)
                            length = int(length_str)
                            audio_data = f.read(length)
                            play_audio_data_for_user(sender_id, audio_data)
                    elif header_line.startswith(b"ID:"):
                        my_client_id = int(header_line.decode('utf-8').split("ID:")[-1])
                except:
                    break

        threading.Thread(target=send_audio).start()
        threading.Thread(target=receive_audio).start()

        # Ensure cleanup when done
        input_stream.stop_stream()
        input_stream.close()
        p.terminate()


# Utility functions for audio playback
def ensure_output_stream(user_id):
    if user_id not in output_streams:
        p = pyaudio.PyAudio()
        out_stream = p.open(format=Format, channels=Channels, rate=Rate, output=True, frames_per_buffer=Chunks)
        output_streams[user_id] = (p, out_stream)
    if user_id not in jitter_buffers:
        jitter_buffers[user_id] = deque()
    if user_id not in playback_threads:
        t = threading.Thread(target=playback_thread_func, args=(user_id,))
        t.daemon = True
        t.start()
        playback_threads[user_id] = t


def playback_thread_func(user_id):
    _, out_stream = output_streams[user_id]
    buffer = jitter_buffers[user_id]

    while not stop_audio_threads:
        if len(buffer) > 0:
            chunk = buffer.popleft()
            out_stream.write(chunk)
        else:
            silence = b'\x00' * (Chunks * 2)
            out_stream.write(silence)
            time.sleep(0.01)


def play_audio_data_for_user(user_id, audio_data):
    ensure_output_stream(user_id)
    jitter_buffers[user_id].append(audio_data)


# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceChatApp(root)
    root.mainloop()
