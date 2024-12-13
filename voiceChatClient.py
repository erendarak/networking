import socket
import threading
import pyaudio
import sys

port = 5000
host = "3.74.41.193"  # Replace with your server's IP

Format = pyaudio.paInt16
Chunks = 4096
Channels = 1
Rate = 44100

# Global variables to control threads
stop_audio_threads = False
stop_input_thread = False

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
        # We've already received the welcome_message upon connecting.
        # Ask the user to input a room choice or NEW:RoomName.
        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
        if choice.lower() == 'q':
            # User wants to quit the application
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        # Check if successfully joined a room
        if "Joined room:" in response:
            return True
        elif "Invalid" in response or "does not exist" in response or "No room chosen" in response:
            # Server will disconnect on invalid choice, so we must reconnect.
            if "Disconnecting" in response:
                client.close()
                return False
            # Otherwise, just loop again
        elif "No rooms available" in response:
            # No rooms yet, user can choose NEW:...
            pass
        else:
            # Unexpected response, just try again.
            pass

def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    The user can type "leave" at any time to stop streaming and return to the menu.
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
        # Continuously read audio from microphone and send it to the server
        while not stop_audio_threads:
            try:
                data = input_stream.read(Chunks, exception_on_overflow=False)
                client.send(data)
            except:
                break

    def receive_audio():
        # Continuously receive audio from the server and play it
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
        # Listen for user typing "leave"
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                break

        # Signal the audio threads to stop
        stop_audio_threads = True
        try:
            client.shutdown(socket.SHUT_RDWR)
        except:
            pass
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

    # Clean up audio streams after stopping
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
            # If we failed to join a room, reconnect and try again
            continue

        # If joined successfully, start streaming
        # The user can type "leave" at any time to go back to the menu
        audio_streaming(client)
        # After user leaves, loop back to allow room selection again.

if __name__ == "__main__":
    main()
