import socket
import threading
import struct

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

rooms = {}  # { room_name: [(conn, user_id), ...] }
broadcast_lock = threading.Lock()  # Lock for broadcasting

next_user_id = 1
user_id_lock = threading.Lock()


def get_next_user_id():
    global next_user_id
    with user_id_lock:
        uid = next_user_id
        next_user_id += 1
    return uid


def start():
    print("Server started, waiting for connections...")
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        t = threading.Thread(target=handle_new_connection, args=(conn,))
        t.start()


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

        # Handle new room creation
        if room_choice.startswith("NEW:"):
            new_room_name = room_choice.split("NEW:")[-1].strip()
            if not new_room_name:
                conn.send(b"Invalid room name. Disconnecting.\n")
                conn.close()
                return

            # If room doesn't exist, create it
            if new_room_name not in rooms:
                rooms[new_room_name] = []
            room_choice = new_room_name

        # Check if the chosen room exists
        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        # Assign a unique user_id to this connection
        user_id = get_next_user_id()

        # Add the client to the chosen room
        rooms[room_choice].append((conn, user_id))
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        handle_client(conn, room_choice, user_id)

    except Exception as e:
        print("Error in handle_new_connection:", e)
        conn.close()


def handle_client(conn, room_name, user_id):
    try:
        while True:
            # Receive audio data from this client
            data = conn.recv(4096)
            if not data:
                break

            # Broadcast the data to all other clients in the same room
            # Put the entire for-loop into the mutex
            packet = struct.pack(">I", user_id) + data  # 4 bytes of user_id, then data
            with broadcast_lock:
                # Broadcast to all others in the room
                for cl, uid in rooms[room_name]:
                    if cl != conn:
                        cl.send(packet)

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Remove the client from the room when disconnected
        for i, (cl, uid) in enumerate(rooms[room_name]):
            if cl == conn:
                del rooms[room_name][i]
                break
        conn.close()
        # If the room is empty, remove it
        if len(rooms[room_name]) == 0:
            del rooms[room_name]
        print(f"Client disconnected from room {room_name}")


start()
