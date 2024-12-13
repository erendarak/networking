import socket
import threading
import pyaudio
import sys

port = 5000
host = "63.176.92.177"  # Replace with your server's IP

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

# Global variables to control threads
stop_audio_threads = False

def connect_to_server():
    client = socket.socket()
    client.connect((host, port))
    welcome_message = client.recv(4096).decode('utf-8')
    return client, welcome_message

def choose_room(client):
    while True:
        print("---------- Main Menu ----------")
        room_list = client.recv(4096).decode('utf-8')
        print(room_list)

        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
        if choice.lower() == 'q':
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        if "Joined room:" in response:
            return True
        elif "Disconnecting" in response:
            client.close()
            return False

def audio_streaming(client):
    global stop_audio_threads
    stop_audio_threads = False

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format, channels=Channels, rate=Rate, input=True, frames_per_buffer=Chunks)
    output_stream = p.open(format=Format, channels=Channels, rate=Rate, output=True, frames_per_buffer=Chunks)

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
                data = client.recv(Chunks)
                if not data:
                    break
                output_stream.write(data)
            except:
                break

    send_thread = threading.Thread(target=send_audio)
    recv_thread = threading.Thread(target=receive_audio)

    send_thread.start()
    recv_thread.start()

    send_thread.join()
    recv_thread.join()

    input_stream.stop_stream()
    input_stream.close()
    output_stream.stop_stream()
    output_stream.close()
    p.terminate()

def main():
    while True:
        client, welcome_message = connect_to_server()
        print(welcome_message)

        if not choose_room(client):
            continue

        audio_streaming(client)

if __name__ == "__main__":
    main()
