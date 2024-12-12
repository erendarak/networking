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

packet_size = 2 + (Chunks * 2)
silence = bytes([0] * (Chunks * 2))

stop_audio_threads = False
sources = defaultdict(Queue)

def connect_to_server():
    client = socket.socket()
    client.connect((host, port))
    welcome_message = client.recv(4096).decode('utf-8')
    return client, welcome_message

def choose_room(client):
    while True:
        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
        if choice.lower() == 'q':
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        if "Joined room:" in response:
            return True

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
        buf = b""
        while not stop_audio_threads:
            try:
                chunk = client.recv(packet_size - len(buf))
                if not chunk:
                    break
                buf += chunk
                if len(buf) == packet_size:
                    sender_id = struct.unpack('>H', buf[:2])[0]
                    audio_data = buf[2:]
                    sources[sender_id].put(audio_data)
                    buf = b""
            except:
                break

    def mixer_thread():
        import time
        while not stop_audio_threads:
            if len(sources) == 0:
                time.sleep(0.01)
                continue

            buffers = []
            for sid, q in list(sources.items()):
                if not q.empty():
                    buffers.append(q.get())
                else:
                    buffers.append(silence)

            sample_arrays = []
            for buf in buffers:
                samples = struct.unpack('<' + ('h' * Chunks), buf)
                sample_arrays.append(samples)

            mixed_samples = []
            for i in range(Chunks):
                s_sum = 0
                for arr in sample_arrays:
                    s_sum += arr[i]

                mixed_value = int(s_sum / len(sample_arrays))
                if mixed_value > 32767:
                    mixed_value = 32767
                elif mixed_value < -32768:
                    mixed_value = -32768
                mixed_samples.append(mixed_value)

            mixed_data = struct.pack('<' + ('h' * Chunks), *mixed_samples)
            output_stream.write(mixed_data)

    t_send = threading.Thread(target=send_audio)
    t_recv = threading.Thread(target=receive_audio)
    t_mix = threading.Thread(target=mixer_thread)

    t_send.start()
    t_recv.start()
    t_mix.start()

    t_send.join()
    t_recv.join()
    t_mix.join()

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
