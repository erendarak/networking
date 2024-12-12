import socket
import threading
import sys
import pyaudio

# Burada host ve port'u sabit değişken olarak belirtiyoruz
HOST = "35.158.171.58"  # Sunucunun IP adresi
PORT = 5000  # Sunucunun portu

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

stop_audio_threads = False


class VoiceChatClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.client.connect((self.host, self.port))
        except:
            print("Couldn't connect to server")
            sys.exit(0)

        self.choose_room()

        self.p = pyaudio.PyAudio()
        self.input_stream = self.p.open(format=Format,
                                        channels=Channels,
                                        rate=Rate,
                                        input=True,
                                        frames_per_buffer=Chunks)

        self.output_stream = self.p.open(format=Format,
                                         channels=Channels,
                                         rate=Rate,
                                         output=True,
                                         frames_per_buffer=Chunks)

        print("Successfully joined the room!")

        # Thread'leri başlat
        self.stop_audio_threads = False
        t_send = threading.Thread(target=self.send_audio)
        t_recv = threading.Thread(target=self.receive_audio)
        t_input = threading.Thread(target=self.user_input_loop)

        t_send.start()
        t_recv.start()
        t_input.start()

        t_send.join()
        t_recv.join()

        self.input_stream.stop_stream()
        self.input_stream.close()
        self.output_stream.stop_stream()
        self.output_stream.close()
        self.p.terminate()

    def choose_room(self):
        # Oda listesi ve talimatları al
        welcome_message = self.client.recv(4096).decode('utf-8')
        print(welcome_message)

        while True:
            choice = input(
                "Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                self.client.close()
                sys.exit(0)

            self.client.send(choice.encode('utf-8'))
            response = self.client.recv(4096).decode('utf-8')
            print(response)

            if "Joined room:" in response:
                # Odaya girdik
                return
            elif "Invalid" in response or "does not exist" in response or "No room chosen" in response:
                if "Disconnecting" in response:
                    # Bağlantı kesilmiş, tekrar deneyemeyiz
                    self.client.close()
                    sys.exit(0)
                # Aksi halde tekrar dene
            elif "No rooms available" in response:
                # Yeni oda oluştur veya tekrar dene
                pass

    def send_audio(self):
        while not self.stop_audio_threads:
            try:
                data = self.input_stream.read(Chunks, exception_on_overflow=False)
                self.client.sendall(data)
            except:
                break

    def receive_audio(self):
        while not self.stop_audio_threads:
            try:
                data = self.client.recv(Chunks)
                if not data:
                    break
                self.output_stream.write(data)
            except:
                break

    def user_input_loop(self):
        # Kullanıcı "leave" yazarsa odayı terk et
        while not self.stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break
        self.stop_audio_threads = True
        try:
            self.client.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.client.close()


if __name__ == "__main__":
    client = VoiceChatClient(HOST, PORT)
