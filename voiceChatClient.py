import socket
import threading
import pyaudio
import sys

host = "3.74.41.193"  # Replace with your EC2 public IP or hostname
port = 5000

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

# Global variables to control threads
stop_audio_threads = False


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
    """
    while True:
        print("---------- Main Menu ----------")
        # Display the server's welcome message
        print(client.recv(4096).decode('utf-8'))

        # Ask the user to input a room choice or NEW:<RoomName>
        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()

        if choice.lower() == 'q':
            # User wants to quit the application
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        # Check if successfully joined or created a room
        if "Joined room:" in response or "created successfully" in response:
            return True


def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    """
    global stop_audio_threads
    stop_audio_threads = False  # Reset flag

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
        while not stop_audio_threads:
            try:
                data = client.recv(Chunks)
                if not data:
                    break
                output_stream.write(data)
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

    # Start threads for send, receive, and user input
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
    output_stream.stop_stream()
    output_stream.close()
    p.terminate()


def main():
    while True:
        # Connect to the server and get the current room list
        client, welcome_message = connect_to_server()
        print(welcome_message)

        # User chooses room or creates a new one
        joined = choose_room(client)
        if not joined:
            continue

        # Start audio streaming
        audio_streaming(client)


if __name__ == "__main__":
    main()
