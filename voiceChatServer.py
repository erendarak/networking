import socket
import threading

port = 5000
host = "0.0.0.0"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen(5)

rooms = {}  # Dictionary: {room_name: [ (conn, client_id), (conn, client_id), ... ] }
client_id_counter = 0
broadcast_lock = threading.Lock()  # lock for broadcasting data

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

        # If the chosen room does not exist and not a NEW request, handle error
        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        # Assign a unique client ID
        global client_id_counter
        client_id_counter += 1
        this_client_id = client_id_counter

        # Add the client to the chosen room
        rooms[room_choice].append((conn, this_client_id))
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))
        # Send the client their ID
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
            # Broadcast the data to all other clients in the same room
            with broadcast_lock:
                for cl, cl_id in rooms[room_name]:
                    if cl != conn:
                        # Send data with the format: DATA:<client_id>:<raw audio>
                        # This ensures the receivers know who sent it.
                        cl.send(b"DATA:" + str(client_id).encode('utf-8') + b":" + data)

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Remove the client from the room when disconnected
        if (conn, client_id) in rooms[room_name]:
            rooms[room_name].remove((conn, client_id))
        conn.close()
        # Optional: if the room is empty, you could remove it from the dictionary
        if len(rooms[room_name]) == 0:
            del rooms[room_name]
        print(f"Client {client_id} disconnected from room {room_name}")

start()
