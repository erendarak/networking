from socket import *
from threading import Thread, Lock
import queue

class EntryThread(Thread):
    def __init__(self, host, port):
        Thread.__init__(self)
        self.address_voice = (host, port)
        self.voice_socket = socket(AF_INET, SOCK_STREAM)
        self.voice_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.voice_socket.bind(self.address_voice)
        self.voice_socket.listen(10)
        print(f"Server listening on {host}:{port}")

    def run(self):
        while True:
            sock_v, data_v = self.voice_socket.accept()
            print(f"New connection from {data_v}")
            ClientHandler(sock_v, data_v).start()

class ClientHandler(Thread):
    def __init__(self, client_socket, address):
        Thread.__init__(self)
        self.client_socket = client_socket
        self.address = address
        self.chunk_size = 1024

    def run(self):
        global clients
        with client_lock:
            clients[self.client_socket] = queue.Queue()  # Create a queue for this client
        print(f"Client {self.address} connected.")

        try:
            while True:
                audio_data = self.client_socket.recv(self.chunk_size)
                if not audio_data:
                    break
                with client_lock:
                    # Add received audio to the queues of all other clients
                    for client, q in clients.items():
                        if client != self.client_socket:
                            q.put(audio_data)
        except Exception as e:
            print(f"Error handling client {self.address}: {e}")
        finally:
            with client_lock:
                del clients[self.client_socket]
            self.client_socket.close()
            print(f"Client {self.address} disconnected.")

class Broadcaster(Thread):
    def run(self):
        global clients
        while True:
            with client_lock:
                for client, q in list(clients.items()):
                    try:
                        while not q.empty():
                            audio_data = q.get_nowait()
                            client.sendall(audio_data)
                    except Exception as e:
                        print(f"Error broadcasting to client: {e}")
                        del clients[client]

clients = {}
client_lock = Lock()

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000

    EntryThread(host, port).start()
    Broadcaster().start()
