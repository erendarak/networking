import socket
import threading
from collections import defaultdict

host = "0.0.0.0"  # Listen on all available interfaces
port = 5000

# Rooms and clients
rooms = defaultdict(list)  # Room name -> List of (client_socket, client_id)
client_id_counter = 0
client_lock = threading.Lock()
broadcast_lock = threading.Lock()

# Constants for protocol
DATA_PREFIX = "DATA:"
ID_PREFIX = "ID:"
WELCOME_MESSAGE = "Welcome to the Voice Chat Server! Available Commands:\n" \
                  "- NEW:<RoomName> to create a room\n" \
                  "- Join an existing room by typing the room name."

def handle_new_connection(conn):
    try:
        room_list = "\n".join(rooms.keys()) if rooms else "No rooms available."
        welcome_msg = (
            "Available rooms:\n" +
            room_list +
            "\n\nType an existing room name to join it, or type 'NEW:<RoomName>' to create a new room:\n"
        )
        conn.send(welcome_msg.encode('utf-8'))

        room_choice = conn.recv(1024).decode('utf-8').strip()

        if room_choice.startswith("NEW:"):
            new_room_name = room_choice.split("NEW:")[-1].strip()
            if not new_room_name:
                conn.send(b"Invalid room name. Disconnecting.\n")
                conn.close()
                return
            if new_room_name not in rooms:
                rooms[new_room_name] = []
            room_choice = new_room_name

        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        global client_id_counter
        with client_lock:
            client_id_counter += 1
            this_client_id = client_id_counter

        rooms[room_choice].append((conn, this_client_id))
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))
        conn.send(f"ID:{this_client_id}\n".encode('utf-8'))

        handle_client(conn, room_choice, this_client_id)

    except Exception as e:
        print("Error in handle_new_connection:", e)
        conn.close()

def handle_client(conn, room_name, client_id):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break

            # Broadcast this audio data to everyone else in the room
            with broadcast_lock:
                for cl, cl_id in rooms[room_name]:
                    if cl != conn:
                        # Send the length-prefixed message:
                        # First a line: "DATA:<client_id>:<length>\n"
                        header = f"DATA:{client_id}:{len(data)}\n".encode('utf-8')
                        cl.send(header + data)

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        if (conn, client_id) in rooms[room_name]:
            rooms[room_name].remove((conn, client_id))
        conn.close()
        if len(rooms[room_name]) == 0:
            del rooms[room_name]
        print(f"Client {client_id} disconnected from room {room_name}")

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
            threading.Thread(target=handle_new_connection, args=(client_socket,), daemon=True).start()
        except Exception as e:
            print(f"Error accepting new connection: {e}")

if __name__ == "__main__":
    server_listener()
