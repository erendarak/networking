import socket
import threading

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

# Dictionary to hold rooms and their client lists
rooms = {
    "A": [],
    "B": []
}


def start():
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")

        # Handle room assignment in a separate thread
        t = threading.Thread(target=handle_new_connection, args=(conn,))
        t.start()


def handle_new_connection(conn):
    try:
        # First, we receive which room the client wants to join
        # The client should send this information immediately upon connecting.
        room_choice = conn.recv(1024).decode('utf-8').strip()

        if room_choice not in rooms:
            # If the requested room doesn't exist, you can handle it by:
            # 1. Defaulting to a specific room
            # 2. Closing the connection
            # 3. Sending an error message back
            #
            # For simplicity, we will default them to room A if invalid:
            room_choice = "A"

        # Add client to the chosen room
        rooms[room_choice].append(conn)
        print(f"Client added to room {room_choice}")

        # Now start handling incoming audio data from this client
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

            # Broadcast the data to all other clients in the same room
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
        print(f"Client disconnected from room {room_name}")


start()
