import socket
import threading
from collections import defaultdict

host = "0.0.0.0"  # Listen on all available interfaces
port = 5000

# Rooms and clients
rooms = defaultdict(dict)  # Room name -> {client_id: client_socket}
client_id_counter = 0
client_lock = threading.Lock()

# Constants for protocol
DATA_PREFIX = "DATA:"
ID_PREFIX = "ID:"
WELCOME_MESSAGE = "Welcome to the Voice Chat Server! Available Commands:\n" \
                  "- NEW:<RoomName> to create a room\n" \
                  "- Join an existing room by typing the room name."

def broadcast_to_room(room_name, sender_id, data):
    """Send audio data to all clients in the room except the sender."""
    if room_name in rooms:
        for client_id, client_socket in rooms[room_name].items():
            if client_id != sender_id:
                try:
                    header = f"{DATA_PREFIX}{sender_id}:{len(data)}\n".encode("utf-8")
                    client_socket.sendall(header + data)
                except Exception as e:
                    print(f"Error sending to client {client_id}: {e}")

def handle_client(client_socket, address):
    global client_id_counter

    client_id = None
    current_room = None
    client_socket_file = client_socket.makefile('rb')

    try:
        # Assign a unique client ID
        with client_lock:
            client_id = client_id_counter
            client_id_counter += 1

        # Send client ID to the client
        client_socket.sendall(f"{ID_PREFIX}{client_id}\n".encode("utf-8"))
        client_socket.sendall(WELCOME_MESSAGE.encode("utf-8"))

        while True:
            line = client_socket_file.readline().strip()
            if not line:
                break

            message = line.decode("utf-8")

            # Room management commands
            if message.startswith("NEW:"):
                room_name = message.split("NEW:")[1]
                if room_name in rooms:
                    client_socket.sendall(f"Room '{room_name}' already exists!\n".encode("utf-8"))
                else:
                    rooms[room_name] = {}
                    rooms[room_name][client_id] = client_socket
                    current_room = room_name
                    client_socket.sendall(f"Created and joined room: {room_name}\n".encode("utf-8"))
            elif message in rooms:
                if current_room:
                    del rooms[current_room][client_id]
                rooms[message][client_id] = client_socket
                current_room = message
                client_socket.sendall(f"Joined room: {message}\n".encode("utf-8"))
            else:
                client_socket.sendall(f"Unknown command or room: {message}\n".encode("utf-8"))

        # Audio data handling
        while True:
            header_line = client_socket_file.readline()
            if not header_line:
                break
            header_line = header_line.strip()

            if header_line.startswith(b"DATA:"):
                parts = header_line.decode("utf-8").split(":")
                if len(parts) == 3:
                    _, sender_id_str, length_str = parts
                    sender_id = int(sender_id_str)
                    length = int(length_str)
                    audio_data = client_socket_file.read(length)
                    if len(audio_data) == length:
                        broadcast_to_room(current_room, sender_id, audio_data)

    except Exception as e:
        print(f"Error with client {client_id} at {address}: {e}")
    finally:
        if current_room and client_id in rooms[current_room]:
            del rooms[current_room][client_id]
        client_socket.close()
        print(f"Client {client_id} at {address} disconnected.")

def server_listener():
    """Main server listener loop to accept new connections."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)

    print(f"Server started on {host}:{port}. Waiting for connections...")

    while True:
        try:
            client_socket, address = server_socket.accept()
            print(f"New connection from {address}")
            threading.Thread(target=handle_client, args=(client_socket, address), daemon=True).start()
        except Exception as e:
            print(f"Error accepting new connection: {e}")

if __name__ == "__main__":
    server_listener()
