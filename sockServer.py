from socket import *
from threading import Thread, Lock

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
            thread = HandleClientThread(sock_v)
            thread.start()

class HandleClientThread(Thread):
    def __init__(self, vsock):
        global clients
        Thread.__init__(self)
        self.chunk = 1024
        self.vsock = vsock
        with mutex:  # Add client to the list
            clients.append(self.vsock)

    def run(self):
        global clients
        while True:
            try:
                audio_data = self.vsock.recv(self.chunk)
                if not audio_data:
                    break
                with mutex:
                    for client in clients:
                        if client != self.vsock:  # Do not send to the sender
                            try:
                                client.sendall(audio_data)
                            except Exception as e:
                                print(f"Error sending audio: {e}")
                                clients.remove(client)
            except Exception as e:
                print(f"Error receiving audio: {e}")
                break
        with mutex:  # Remove client on disconnect
            clients.remove(self.vsock)
            print(f"Client disconnected")

mutex = Lock()
clients = []

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 5000

    server = EntryThread(host, port)
    server.start()
    server.join()
