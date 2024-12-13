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
            thread = HandleClientThread(sock_v, data_v)
            thread.start()


class HandleClientThread(Thread):
    def __init__(self, vsock, vdata):
        global clients
        Thread.__init__(self)
        self.chunk = 1024
        self.vsock = vsock
        self.vdata = vdata
        self.name = self.vsock.recv(self.chunk).decode()
        print(f"Client registered: {self.name}")
        with mutex:  # Add client in a thread-safe manner
            clients[self.name] = {'address': self.vdata, 'socket': self.vsock, 'buffer': []}

    def run(self):
        global clients
        while True:
            try:
                audio_data = self.vsock.recv(self.chunk)
                if not audio_data:
                    break
                with mutex:  # Access client data in a thread-safe manner
                    for client_name, client_info in clients.items():
                        if client_info['address'][1] != self.vdata[1]:  # Recipient != sender
                            client_info['buffer'].append(audio_data)  # Add data to recipient's buffer
            except Exception as e:
                print(f"Error: {e}")
                break
        # Remove client on disconnection
        with mutex:
            print(f"Client {self.name} disconnected")
            clients.pop(self.name, None)


# Separate thread to handle sending data from buffers
class BroadcastThread(Thread):
    def run(self):
        while True:
            with mutex:
                for client_name, client_info in clients.items():
                    buffer = client_info['buffer']
                    if buffer:
                        try:
                            for data_chunk in buffer:
                                client_info['socket'].send(data_chunk)
                            client_info['buffer'].clear()  # Clear buffer after sending
                        except Exception as e:
                            print(f"Error broadcasting to {client_name}: {e}")
                            # Handle client disconnection
                            clients.pop(client_name, None)
                            break


mutex = Lock()
clients = {}

if __name__ == "__main__":
    # AWS-friendly host and port
    host = "0.0.0.0"
    port = 5000

    # Start the server thread
    server = EntryThread(host, port)
    server.start()

    # Start the broadcasting thread
    broadcaster = BroadcastThread()
    broadcaster.start()

    server.join()
    broadcaster.join()
