import socket
import threading
import collections

# Server configuration
port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

# Rooms and thread locks
rooms = {}  # {room_name: [clients]}
locks = collections.defaultdict(threading.Lock)  # One lock per room

def start():
    print("Server started, waiting for connections...")
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        threading.Thread(target=handle_new_connection, args=(conn,)).start()

def handle_new_connection(conn):
    try:
        # Send the list of current rooms and instructions
        room_list = "\n".join(rooms.keys()) if rooms else "No rooms available."
        welcome_msg = (
            "Available rooms:\n" +
            room_list +
            "\n\nType an existing room name to join it, or type 'NEW:<RoomName>' to create a new room:\n"
        )
        conn.send(welcome_msg.encode('utf-8'))

        # Receive the room choice or new room request
        room_choice = conn.recv(1024).decode('utf-8').strip()

        if room_choice.startswith("NEW:"):
            new_room_name = room_choice.split("NEW:")[-1].strip()
            if not new_room_name:
                conn.send(b"Invalid room name. Disconnecting.\n")
                conn.close()
                return

            with locks[new_room_name]:  # Ensure thread-safe room creation
                if new_room_name not in rooms:
                    rooms[new_room_name] = []
            room_choice = new_room_name

        if room_choice not in rooms:
            conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        with locks[room_choice]:
            rooms[room_choice].append(conn)
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

            with locks[room_name]:  # Ensure thread-safe broadcast
                for cl in rooms[room_name]:
                    if cl != conn:
                        try:
                            cl.send(data)
                        except Exception as e:
                            print(f"Error sending to client: {e}")
    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        with locks[room_name]:
            if conn in rooms[room_name]:
                rooms[room_name].remove(conn)
            if not rooms[room_name]:
                del rooms[room_name]
        conn.close()
        print(f"Client disconnected from room {room_name}")

start()
