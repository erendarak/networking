import socket
import threading
import pyaudio
import sys
import struct
from collections import defaultdict
from queue import Queue

host = "35.158.171.58"
port = 5000

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

# Global variables to control threads
stop_audio_threads = False
stop_input_thread = False

# Her kaynaktan gelen veriyi tutacak yapılar
# sources = { id: Queue() }
sources = defaultdict(Queue)

def connect_to_server():
    """Connects to the server and returns the socket and the welcome message."""
    client = socket.socket()
    client.connect((host, port))
    welcome_message = client.recv(4096).decode('utf-8')
    return client, welcome_message

def choose_room(client):
    while True:
        print("---------- Main Menu ----------")
        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
        if choice.lower() == 'q':
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        if "Joined room:" in response:
            return True
        elif "Invalid" in response or "does not exist" in response or "No room chosen" in response:
            if "Disconnecting" in response:
                client.close()
                return False
        elif "No rooms available" in response:
            pass

def audio_streaming(client):
    global stop_audio_threads
    stop_audio_threads = False

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format,
                          channels=Channels,
                          rate=Rate,
                          input=True,
                          frames_per_buffer=Chunks)

    output_stream = p.open(format=Format,
                           channels=Channels,
                           rate=Rate,
                           output=True,
                           frames_per_buffer=Chunks)

    def send_audio():
        while not stop_audio_threads:
            try:
                data = input_stream.read(Chunks, exception_on_overflow=False)
                client.send(data)
            except:
                break

    def receive_audio():
        # Bu thread her gelen paketi alır:
        # Packet format: 2 byte ID + 4096 byte audio
        packet_size = 2 + Chunks
        buf = b""
        while not stop_audio_threads:
            try:
                chunk = client.recv(packet_size - len(buf))
                if not chunk:
                    break
                buf += chunk
                if len(buf) == packet_size:
                    # Paket tamam
                    # İlk 2 byte ID, kalan 4096 byte ses
                    sender_id = struct.unpack('>H', buf[:2])[0]
                    audio_data = buf[2:]
                    # audio_data: 4096 byte
                    # Kaynak kuyruğuna ekle
                    sources[sender_id].put(audio_data)
                    buf = b""
            except:
                break

    def mixer_thread():
        # Belirli aralıklarla tüm kaynaklardan veri çekip miksle
        # Sessizlik = 4096 byte sıfır
        silence = bytes([0]*(Chunks))
        import time

        while not stop_audio_threads:
            # sources sözlüğündeki tüm ID'leri al
            # Eğer hiçbir source yoksa bekle
            if len(sources) == 0:
                time.sleep(0.01)
                continue

            # Her kaynaktan 4096 byte çek veya sessizlik
            buffers = []
            for sid, q in list(sources.items()):
                if not q.empty():
                    buffers.append(q.get())
                else:
                    buffers.append(silence)

            # buffers şimdi birden çok kaynağın 4096 byte'ını içeriyor
            # Mix et (16-bit signed integer)
            # Her buffers öğesini int16 array'e dönüştür
            sample_arrays = []
            for buf in buffers:
                samples = struct.unpack('<' + ('h'*Chunks), buf)
                sample_arrays.append(samples)

            mixed_samples = []
            for i in range(Chunks):
                s_sum = 0
                for arr in sample_arrays:
                    s_sum += arr[i]
                # Clamping
                if s_sum > 32767:
                    s_sum = 32767
                elif s_sum < -32768:
                    s_sum = -32768
                mixed_samples.append(s_sum)

            mixed_data = struct.pack('<' + ('h'*Chunks), *mixed_samples)
            output_stream.write(mixed_data)

    def user_input():
        global stop_audio_threads
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break

        stop_audio_threads = True
        try:
            client.shutdown(socket.SHUT_RDWR)
        except:
            pass
        client.close()

    t_send = threading.Thread(target=send_audio)
    t_recv = threading.Thread(target=receive_audio)
    t_mix = threading.Thread(target=mixer_thread)
    t_input = threading.Thread(target=user_input)

    t_send.start()
    t_recv.start()
    t_mix.start()
    t_input.start()

    t_send.join()
    t_recv.join()
    t_mix.join()
    # t_input beklemeden de kapatılabilir.
    # user_input thread sonlanınca buraya gelir.

    input_stream.stop_stream()
    input_stream.close()
    output_stream.stop_stream()
    output_stream.close()
    p.terminate()

def main():
    while True:
        client, welcome_message = connect_to_server()
        print(welcome_message)

        joined = choose_room(client)
        if not joined:
            continue

        audio_streaming(client)

if __name__ == "__main__":
    main()
