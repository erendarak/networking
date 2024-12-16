import socket
import threading

port = 5000
host = "0.0.0.0"

server = socket.socket()
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
                audio_channels[new_room_name] = {}  # Create audio channels for the new room
            room_choice = new_room_name

        if room_choice not in rooms:
            conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        rooms[room_choice].append(conn)
        client_id = len(audio_channels[room_choice]) + 1
        audio_channels[room_choice][conn] = client_id  # Assign a unique channel to the client
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        handle_client(conn, room_choice)
    except Exception as e:
        print("Error in handle_new_connection:", e)
        conn.close()


def handle_client(conn, room_name):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break

            client_id = audio_channels[room_name][conn]
            broadcast_to_room(conn, room_name, data, client_id)
    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        remove_client(conn, room_name)


def broadcast_to_room(sender_conn, room_name, data, client_id):
    try:
        for client_conn in rooms[room_name]:
            if client_conn != sender_conn:
                client_conn.send(f"{client_id}|".encode('utf-8') + data)
    except Exception as e:
        print(f"Error in broadcast_to_room: {e}")


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
