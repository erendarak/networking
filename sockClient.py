import socket
import threading
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class VoiceChatClient:
    def __init__(self, host, port):
        self.server_address = (host, port)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=FORMAT,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      output=True,
                                      frames_per_buffer=CHUNK)
        self.running = True

    def connect(self):
        try:
            self.client_socket.connect(self.server_address)
            print(f"Connected to server at {self.server_address}")
        except Exception as e:
            print(f"Failed to connect: {e}")
            self.running = False

    def send_audio(self):
        while self.running:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                self.client_socket.sendall(data)
            except Exception as e:
                print(f"Error sending audio: {e}")
                self.running = False
                break

    def receive_audio(self):
        while self.running:
            try:
                data = self.client_socket.recv(CHUNK)
                if data:
                    self.stream.write(data)
            except Exception as e:
                print(f"Error receiving audio: {e}")
                self.running = False
                break

    def start(self):
        self.connect()
        if self.running:
            send_thread = threading.Thread(target=self.send_audio)
            recv_thread = threading.Thread(target=self.receive_audio)
            send_thread.start()
            recv_thread.start()
            send_thread.join()
            recv_thread.join()

    def stop(self):
        self.running = False
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        self.client_socket.close()
        print("Disconnected from server")

if __name__ == "__main__":
    # Replace with the public IP of your AWS server
    host = "3.74.41.193"
    port = 5000

    client = VoiceChatClient(host, port)
    try:
        client.start()
    except KeyboardInterrupt:
        client.stop()
