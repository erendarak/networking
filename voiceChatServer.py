import socket
import threading

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

rooms = {}  # Dictionary: { "room_name": [list_of_client_sockets] }
room_locks = {}  # Dictionary: { "room_name": threading.Lock() } to control broadcasts
broadcast_lock = threading.Lock()  # Global lock for broadcasting (alternative: per-room lock)

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
                room_locks[new_room_name] = threading.Lock()  # Create a lock for this new room
            room_choice = new_room_name

        # Check if the chosen room exists
        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        # Add the client to the chosen room
        rooms[room_choice].append(conn)
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        handle_client(conn, room_choice)

    except Exception as e:
        print("Error in handle_new_connection:", e)
        conn.close()

def handle_client(conn, room_name):
    try:
        while True:
            # Receive audio data from this client
            data = conn.recv(4096)
            if not data:
                break

            # Broadcast the data to all other clients in the same room without interleaving
            # We use a mutex (lock) here to ensure no two broadcasts happen at once.
            with broadcast_lock:
                # Only one thread can enter this block at a time.
                for cl in rooms[room_name]:
                    if cl != conn:
                        cl.send(data)

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Remove the client from the room when disconnected
        if conn in rooms[room_name]:
            rooms[room_name].remove(conn)
        conn.close()
        # If the room is empty, remove it
        if len(rooms[room_name]) == 0:
            del rooms[room_name]
            # Also delete the associated lock
            if room_name in room_locks:
                del room_locks[room_name]
        print(f"Client disconnected from room {room_name}")

start()
