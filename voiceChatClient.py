import socket
import threading
import pyaudio
import sys

host = "18.195.99.124"
port = 5000

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

stop_audio_threads = False


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
        elif "Invalid" in response or "does not exist" in response or "No room chosen" in response:
            continue


def audio_streaming(client):
    global stop_audio_threads
    stop_audio_threads = False

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format, channels=Channels, rate=Rate, input=True, frames_per_buffer=Chunks)
    output_streams = {}

    def send_audio():
        while not stop_audio_threads:
            try:
                data = input_stream.read(Chunks, exception_on_overflow=False)
                client.send(data)
            except:
                break

    def receive_audio():
        while not stop_audio_threads:
            try:
                data = client.recv(Chunks + 10)
                if not data:
                    break

                # Parse the client ID and audio data
                client_id, audio_data = data.split(b"|", 1)
                client_id = int(client_id.decode('utf-8'))

                if client_id not in output_streams:
                    output_streams[client_id] = p.open(format=Format, channels=Channels, rate=Rate, output=True, frames_per_buffer=Chunks)

                output_streams[client_id].write(audio_data)
            except:
                break

    def user_input():
        global stop_audio_threads
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break

        stop_audio_threads = True
        client.close()

    t_send = threading.Thread(target=send_audio)
    t_recv = threading.Thread(target=receive_audio)
    t_input = threading.Thread(target=user_input)

    t_send.start()
    t_recv.start()
    t_input.start()

    t_send.join()
    t_recv.join()

    input_stream.stop_stream()
    input_stream.close()
    for stream in output_streams.values():
        stream.stop_stream()
        stream.close()
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
