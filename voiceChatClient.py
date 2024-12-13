import socket
import threading
import pyaudio
import sys
import struct

port = 5000
host = "3.74.41.193"  # Replace with your server's IP

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
            # Server likely disconnected. Need to reconnect.
            if "Disconnecting" in response:
                client.close()
                return False
        elif "No rooms available" in response:
            # Try again, user can create a new room.
            pass
        else:
            # Unexpected response, try again.
            pass

def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    Each sender has its own audio output stream.
    The user can type "leave" to return to the menu.
    """
    global stop_audio_threads
    stop_audio_threads = False  # Reset flag

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format,
                          channels=Channels,
                          rate=Rate,
                          input=True,
                          frames_per_buffer=Chunks)

    # Dictionary of user_id -> output_stream
    output_streams = {}

    def get_output_stream(user_id):
        """Get or create an output stream for the given user_id."""
        if user_id not in output_streams:
            out_stream = p.open(format=Format,
                                channels=Channels,
                                rate=Rate,
                                output=True,
                                frames_per_buffer=Chunks)
            output_streams[user_id] = out_stream
        return output_streams[user_id]

    def send_audio():
        # Continuously read audio from microphone and send it to the server
        while not stop_audio_threads:
            try:
                data = input_stream.read(Chunks, exception_on_overflow=False)
                client.send(data)
            except:
                break

    def receive_audio():
        # Continuously receive data from the server
        while not stop_audio_threads:
            try:
                # First, read 4 bytes of user_id
                header = b''
                while len(header) < 4:
                    chunk = client.recv(4 - len(header))
                    if not chunk:
                        return
                    header += chunk
                if len(header) < 4:
                    # Connection closed
                    return

                user_id = struct.unpack(">I", header)[0]

                # Now read the audio data (one Chunks frame)
                audio_data = b''
                while len(audio_data) < Chunks:
                    chunk = client.recv(Chunks - len(audio_data))
                    if not chunk:
                        return
                    audio_data += chunk

                # Write the data to the correct output stream
                out_stream = get_output_stream(user_id)
                out_stream.write(audio_data)
            except:
                break

    def user_input():
        global stop_audio_threads
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break

        # Stop threads and close client
        stop_audio_threads = True
        try:
            client.shutdown(socket.SHUT_RDWR)
        except:
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

    # Close all streams after stopping
    input_stream.stop_stream()
    input_stream.close()

    for uid, out_stream in output_streams.items():
        out_stream.stop_stream()
        out_stream.close()

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
