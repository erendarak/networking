import socket
import threading
import pyaudio
import sys

host = "18.197.204.63"
port = 5000

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
    If an invalid choice is made, re-try until a valid one.
    Returns True if a room was successfully joined, False otherwise.
    """
    while True:
        print("---------- Main Menu ----------")
        # Server has already sent the welcome message listing available rooms
        # Re-fetch the server message since after leaving we re-connected
        # (This is handled outside and passed here)
        # Actually, we need to re-receive it if we want a refreshed list.
        # Let's assume the server sends us a fresh menu each connection.
        # If we need a refreshed list after leaving, we can rely on re-connecting.

        # By the time we get here, we've received the welcome_message in main().
        # It's in a variable accessible to choose_room.

        # Ask the user to input a room choice or NEW:RoomName
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
            # Invalid choice, the server disconnected? According to the server code, it might disconnect.
            # If the server disconnects on error, we must reconnect.
            # Let's handle the scenario: if response indicates disconnect,
            # re-connect and start over.
            if "Disconnecting" in response:
                client.close()
                return False
            # Otherwise, just loop and ask again since we remain connected.
        elif "No rooms available" in response:
            # User can choose NEW:... or try again.
            # The server still awaits a valid choice, so just loop again.
            pass
        else:
            # If we get here, maybe the response is unexpected.
            # Just loop again and try.
            pass

def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    Also starts a separate thread to listen for 'leave' command from the user.
    When 'leave' is typed, streaming stops and we return to the main menu.
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
        global stop_audio_threads  # Indicate we are using the global variable
        while not stop_audio_threads:
            command = sys.stdin.readline().strip().lower()
            if command == "leave":
                # User wants to leave the room, stop the audio threads
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
    # user_input thread ends when stop_audio_threads is set to True
    # or user_input ends after user types leave.

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

        # User chooses room or creates new one
        joined = choose_room(client)
        if not joined:
            # If we failed to join a room (maybe user typed invalid input and server disconnected),
            # just continue the loop, which reconnects and tries again.
            continue

        # If joined successfully, start streaming
        # The user can type "leave" at any time to go back to the menu
        audio_streaming(client)
        # After user leaves, we end up here and the loop restarts
        # letting the user choose a new room again.

if __name__ == "__main__":
    main()
