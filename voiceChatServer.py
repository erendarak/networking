import socket
import threading
import struct

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)  # Enable TCP keep-alive
server.bind((host, port))
server.listen(5)

rooms = {}  # Dictionary to store rooms and their clients
audio_channels = {}  # Dictionary to store individual audio channels per room


def start():
    print("Server started, waiting for connections...")
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        t = threading.Thread(target=handle_new_connection, args=(conn,))
        t.start()


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
                audio_channels[new_room_name] = {}
            room_choice = new_room_name

        if room_choice not in rooms:
            conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        rooms[room_choice].append(conn)
        client_id = len(audio_channels[room_choice]) + 1
        audio_channels[room_choice][conn] = client_id
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        handle_client(conn, room_choice)
    except Exception as e:
        print(f"Error in handle_new_connection: {e}")
        conn.close()


def handle_client(conn, room_name):
    try:
        while True:
            header = conn.recv(8)  # Header size: 8 bytes (4 bytes client_id, 4 bytes frame_size)
            if not header:
                break

            client_id, frame_size = struct.unpack('!II', header)  # Unpack header
            audio_data = conn.recv(frame_size)

            if not audio_data or len(audio_data) != frame_size:
                print(f"Incomplete audio frame received: expected {frame_size} bytes, got {len(audio_data)}")
                break

            broadcast_to_room(conn, room_name, client_id, audio_data)
    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"Client abruptly disconnected: {e}")
    except Exception as e:
        print(f"Unexpected error in handle_client: {e}")
    finally:
        remove_client(conn, room_name)


def broadcast_to_room(sender_conn, room_name, client_id, audio_data):
    for client_conn in rooms[room_name]:
        if client_conn != sender_conn:
            try:
                header = struct.pack('!II', client_id, len(audio_data))
                client_conn.send(header + audio_data)
            except (BrokenPipeError, ConnectionResetError):
                print(f"Removing client due to broken pipe: {client_conn}")
                remove_client(client_conn, room_name)


def remove_client(conn, room_name):
    if conn in rooms[room_name]:
        rooms[room_name].remove(conn)
    if conn in audio_channels[room_name]:
        del audio_channels[room_name][conn]
    conn.close()
    if len(rooms[room_name]) == 0:
        del rooms[room_name]
        del audio_channels[room_name]
    print(f"Client disconnected from room {room_name}")


start()
