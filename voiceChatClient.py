import socket
import threading
import pyaudio
import sys
from collections import defaultdict

port = 5000
host = "63.176.92.177"  # Replace with your server's IP

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

# Global variables to control threads
stop_audio_threads = False
output_streams = defaultdict(lambda: None)  # Store output streams for each user


def connect_to_server():
    """Connects to the server and returns the socket and the welcome message."""
    client = socket.socket()
    client.connect((host, port))
    welcome_message = client.recv(4096).decode('utf-8')
    return client, welcome_message


def choose_room(client):
    """
    Interactively choose or create a room.
    If an invalid choice is made, re-try until a valid one.
    Returns True if a room was successfully joined, False otherwise.
    """
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
            pass
        elif "No rooms available" in response:
            pass


def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    Each user's audio is handled independently and sent to others.
    """
    global stop_audio_threads
    global output_streams
    stop_audio_threads = False

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format,
                          channels=Channels,
                          rate=Rate,
                          input=True,
                          frames_per_buffer=Chunks)

    def send_audio():
        while not stop_audio_threads:
            try:
                data = input_stream.read(Chunks, exception_on_overflow=False)
                client.send(data)
            except Exception as e:
                print("Error in sending audio:", e)
                break

    def receive_audio():
        while not stop_audio_threads:
            try:
                data = client.recv(Chunks)
                if not data:
                    break

                # Play incoming audio data
                if threading.current_thread() not in output_streams:
                    output_streams[threading.current_thread()] = p.open(format=Format,
                                                                        channels=Channels,
                                                                        rate=Rate,
                                                                        output=True,
                                                                        frames_per_buffer=Chunks)
                output_streams[threading.current_thread()].write(data)
            except Exception as e:
                print("Error in receiving audio:", e)
                break

    def user_input():
        global stop_audio_threads
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break

        stop_audio_threads = True
        try:
            client.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
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
        if stream:
            stream.stop_stream()
            stream.close()
    output_streams.clear()
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