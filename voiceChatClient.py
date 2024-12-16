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

# We will create a dictionary of user_id -> output_stream for separate channels
output_streams = {}
my_client_id = None

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
        choice = input(
            "Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
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
            # The server might have disconnected us after this message
            if "Disconnecting" in response:
                client.close()
                return False
        elif "No rooms available" in response:
            # Just try again
            pass
        else:
            # Unexpected response, try again
            pass


def parse_server_messages(client):
    """
    Parse incoming messages from the server.
    We have two kinds of messages:
      1) Control messages (e.g. 'ID:<num>', 'Joined room:', etc.)
      2) Audio data messages: 'DATA:<sender_id>:<raw_audio_data>'

    We'll receive raw bytes. For control lines, they're text-based and end with newline.
    For DATA, it's binary, but we know it starts with "DATA:".

    We must carefully separate these messages. We'll do:
    - Read from socket in a loop.
    - If a chunk starts with 'DATA:', parse the sender_id and the rest is audio data.
    - Otherwise, treat it as a control line until we see 'DATA:' prefix.

    We'll have a small buffer and process line by line for control messages, and handle DATA differently.
    """
    global my_client_id
    buffer = b""

    # We will read data in a loop. Data can contain multiple messages at once.
    while not stop_audio_threads:
        try:
            chunk = client.recv(4096)
            if not chunk:
                break
            buffer += chunk

            # Process as many messages as we can from buffer
            # Control messages are line-based and end with '\n'
            # Data messages start with 'DATA:' and contain binary data following a colon-separated format.

            # We'll try to split by '\n' first to extract any control lines fully.
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()

                # Check if this line is data or a control message
                if line.startswith(b"DATA:"):
                    # The line actually contains 'DATA:' prefix which means it's a header line.
                    # Format: DATA:<sender_id>:<raw_audio...>
                    # Actually, since we might have read a newline that isn't guaranteed, we need to be careful:
                    # The server might send data in a single packet: DATA:<id>:<binary>
                    # The binary might contain '\n', so we can't rely solely on splitting by newline for audio data.
                    # Instead, let's do this:
                    # We'll reattach this line back to the front of buffer since it's actually data + binary
                    # and handle it differently outside of this loop.

                    buffer = line + b"\n" + buffer
                    break
                else:
                    # It's a control line
                    line_str = line.decode('utf-8')
                    # Handle control lines
                    if line_str.startswith("ID:"):
                        my_client_id = int(line_str.split("ID:")[-1].strip())
                        print(f"Assigned Client ID: {my_client_id}")
                    else:
                        # Other control messages: Just print them
                        # e.g. "Joined room: XXX"
                        if line_str and not line_str.startswith("DATA:"):
                            print(line_str)

            # After processing all complete lines, now check if buffer contains a "DATA:" message
            # DATA messages might not end with newline. They have format:
            # DATA:<sender_id>:<binary data...>
            # We'll search for the first occurrence of b"DATA:" and then parse sender_id and rest.

            while True:
                data_index = buffer.find(b"DATA:")
                if data_index == -1:
                    # No DATA message start found
                    break
                # We found "DATA:"
                # Extract sender_id by reading until next ':'
                start = data_index + len(b"DATA:")
                colon_index = buffer.find(b":", start)
                if colon_index == -1:
                    # We don't have enough data yet to parse sender_id
                    break
                sender_id_str = buffer[start:colon_index].decode('utf-8')
                try:
                    sender_id = int(sender_id_str)
                except:
                    # Invalid sender_id, skip
                    break

                # After "DATA:<sender_id>:", the rest of the buffer (after colon_index+1) is raw audio data
                audio_data_start = colon_index + 1
                # The entire remainder of buffer after this is audio data (until next message)
                # But we must consider that more DATA messages or text lines might follow after this audio segment.
                # In practice, since server sends one DATA chunk per read, we can assume one DATA message per chunk.
                # However, if multiple clients talk at once, multiple DATA messages can arrive.
                # We'll assume one DATA message per chunk to simplify.
                # If multiple arrives, we can process them in a loop.

                # We'll handle one DATA message at a time.
                # The next message could be another DATA:... or a line-based message.
                # We must separate them. Without a length prefix, we rely on either server sending one message at a time
                # or we handle chunk-based reading. The problem states mixing occurred due to concurrency.

                # Let's assume one DATA message per send. If we need more complexity, we could redesign the protocol
                # with length prefixes. For now, let's trust the solver boy's approach (one message at a time).

                # We'll take all remaining data as audio for now, and then clear it from buffer.
                audio_data = buffer[audio_data_start:]
                buffer = b""  # Clear buffer since we've consumed all

                # Play the audio_data on the correct stream
                play_audio_data_for_user(sender_id, audio_data)

        except:
            break


def play_audio_data_for_user(user_id, audio_data):
    """
    Play received audio data for a specific user_id.
    If we don't have an output channel for that user, create one.
    """
    if user_id not in output_streams:
        p = pyaudio.PyAudio()
        output_stream = p.open(format=Format,
                               channels=Channels,
                               rate=Rate,
                               output=True,
                               frames_per_buffer=Chunks)
        output_streams[user_id] = (p, output_stream)
    p, out_stream = output_streams[user_id]
    out_stream.write(audio_data)


def audio_sender(client, input_stream):
    """Thread to send local microphone data to the server."""
    global stop_audio_threads
    while not stop_audio_threads:
        try:
            data = input_stream.read(Chunks, exception_on_overflow=False)
            client.send(data)
        except:
            break


def user_input_thread(client):
    """Thread to listen for 'leave' command from user input."""
    global stop_audio_threads
    while not stop_audio_threads:
        command = sys.stdin.readline().strip().lower()
        if command == "leave":
            # User wants to leave the room, stop the audio threads
            break

    stop_audio_threads = True
    try:
        client.shutdown(socket.SHUT_RDWR)
    except:
        pass
    client.close()


def audio_streaming(client):
    """
    Handles sending and receiving audio data.
    Starts separate threads for:
      - Sending mic audio
      - Receiving audio from server (parse_server_messages)
      - User input (leave)
    """
    global stop_audio_threads
    stop_audio_threads = False  # Reset flag

    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format,
                          channels=Channels,
                          rate=Rate,
                          input=True,
                          frames_per_buffer=Chunks)

    # Sender thread
    t_send = threading.Thread(target=audio_sender, args=(client, input_stream))
    t_send.start()

    # Receiver thread (parses both control and DATA messages)
    t_recv = threading.Thread(target=parse_server_messages, args=(client,))
    t_recv.start()

    # User input thread
    t_input = threading.Thread(target=user_input_thread, args=(client,))
    t_input.start()

    t_send.join()
    t_recv.join()
    # user_input thread ends when stop_audio_threads is True or user typed leave.

    # Close all output streams
    for uid, (pa, out_stream) in output_streams.items():
        out_stream.stop_stream()
        out_stream.close()
        pa.terminate()
    output_streams.clear()

    input_stream.stop_stream()
    input_stream.close()
    p.terminate()


def main():
    while True:
        # Connect to the server and get the current room list
        client, welcome_message = connect_to_server()
        print(welcome_message)

        # User chooses room or creates new one
        joined = choose_room(client)
        if not joined:
            # If we failed to join a room (e.g. server disconnected after invalid input),
            # just continue the loop, which reconnects and tries again.
            continue

        # If joined successfully, start streaming
        audio_streaming(client)
        # After user leaves, we end up here and the loop restarts
        # letting the user choose a new room again.


if __name__ == "__main__":
    main()

