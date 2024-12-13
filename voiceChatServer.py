import socket
import threading
from collections import defaultdict

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

rooms = defaultdict(list)  # Dictionary to store room members
buffers = defaultdict(lambda: defaultdict(bytes))  # Buffers for audio data


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
            data = conn.recv(4096)
            if not data:
                break

            # Add received data to buffer
            buffers[room_name][conn] = data

            # Distribute the data to all other clients
            distribute_audio(room_name, conn)

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Remove the client from the room when disconnected
        if conn in rooms[room_name]:
            rooms[room_name].remove(conn)
        if conn in buffers[room_name]:
            del buffers[room_name][conn]
        conn.close()
        # If the room is empty, remove it
        if len(rooms[room_name]) == 0:
            del rooms[room_name]
            del buffers[room_name]
        print(f"Client disconnected from room {room_name}")


def distribute_audio(room_name, sender_conn):
    """
    Sends a mix of all other clients' audio data to each client in the room.
    """
    for client in rooms[room_name]:
        if client != sender_conn:
            try:
                # Combine all other clients' buffers except the recipient's own
                mixed_audio = b"".join(buffers[room_name][other] for other in buffers[room_name] if other != client)
                client.send(mixed_audio)
            except Exception as e:
                print("Error broadcasting to client:", e)

start()