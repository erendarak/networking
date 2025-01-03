import socket
import threading

class VoiceChatServer:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rooms = {}
        self.lock = threading.Lock()

    def start_server(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")
        while True:
            client_socket, address = self.server_socket.accept()
            print(f"New connection from {address}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        client_id = threading.current_thread().ident
        current_room = None

        while True:
            try:
                message = client_socket.recv(4096).decode('utf-8')

                if message.startswith("NEW:"):
                    room_name = message.split(":", 1)[1].strip()
                    with self.lock:
                        if room_name not in self.rooms:
                            self.rooms[room_name] = []
                        self.rooms[room_name].append((client_socket, client_id))
                    client_socket.send(f"Joined room: {room_name}".encode('utf-8'))
                    current_room = room_name

                elif message == "LIST":
                    with self.lock:
                        room_list = "\n".join(self.rooms.keys())
                    client_socket.send(room_list.encode('utf-8'))

                elif message == "LEAVE":
                    if current_room:
                        with self.lock:
                            self.rooms[current_room] = [c for c in self.rooms[current_room] if c[0] != client_socket]
                            if not self.rooms[current_room]:
                                del self.rooms[current_room]
                        client_socket.send(b"Left the room.")
                        current_room = None

                elif current_room:
                    with self.lock:
                        for sock, _ in self.rooms[current_room]:
                            if sock != client_socket:
                                sock.send(message.encode('utf-8'))

            except (ConnectionResetError, BrokenPipeError):
                break

        if current_room:
            with self.lock:
                self.rooms[current_room] = [c for c in self.rooms[current_room] if c[0] != client_socket]
                if not self.rooms[current_room]:
                    del self.rooms[current_room]

        client_socket.close()

if __name__ == "__main__":
    server = VoiceChatServer()
    server.start_server()