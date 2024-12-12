import socket
import threading

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

clients = []  # Renamed the variable to clients for clarity


def start():
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        clients.append(conn)
        t = threading.Thread(target=handle_client, args=(conn,))
        t.start()


def handle_client(fromConnection):
    try:
        while True:
            data = fromConnection.recv(4096)

            # If data is empty, the client closed the connection
            if not data:
                break

            # Broadcast the data to all other connected clients
            for cl in clients:
                if cl != fromConnection:
                    cl.send(data)

    except Exception as e:
        # Handle any error that occurs during receiving/sending data
        print("Error or disconnection:", e)

    finally:
        # Remove the disconnected client from the list
        if fromConnection in clients:
            clients.remove(fromConnection)
        fromConnection.close()
        print("Client Disconnected")


start()
