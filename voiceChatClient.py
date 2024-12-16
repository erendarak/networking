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

output_streams = {}
my_client_id = None
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
        elif "Disconnecting" in response:
            client.close()
            return False
        # otherwise, loop again

def play_audio_data_for_user(user_id, audio_data):
    if user_id not in output_streams:
        p = pyaudio.PyAudio()
        out_stream = p.open(format=Format,
                            channels=Channels,
                            rate=Rate,
                            output=True,
                            frames_per_buffer=Chunks)
        output_streams[user_id] = (p, out_stream)
    p, out_stream = output_streams[user_id]
    out_stream.write(audio_data)

def parse_server_messages(client):
    global stop_audio_threads, my_client_id

    # We'll use a loop that reads one line at a time for control or DATA header
    # When we get DATA header, we read exactly <length> bytes.
    f = client.makefile('rb')  # makefile for easier line reading
    while not stop_audio_threads:
        try:
            header_line = f.readline()
            if not header_line:
                break
            header_line = header_line.strip()
            if header_line.startswith(b"DATA:"):
                # Format: DATA:<sender_id>:<length>
                parts = header_line.decode('utf-8').split(':')
                if len(parts) == 3:
                    _, sender_id_str, length_str = parts
                    sender_id = int(sender_id_str)
                    length = int(length_str)
                    # Now read exactly 'length' bytes of audio data
                    audio_data = f.read(length)
                    if not audio_data or len(audio_data) < length:
                        # Connection interrupted or incomplete read
                        break
                    play_audio_data_for_user(sender_id, audio_data)
            elif header_line.startswith(b"ID:"):
                # Assign my_client_id
                line_str = header_line.decode('utf-8')
                my_client_id = int(line_str.split("ID:")[-1])
                print(f"Assigned Client ID: {my_client_id}")
            else:
                # Control message, just print
                line_str = header_line.decode('utf-8')
                if line_str:
                    print(line_str)
        except Exception as e:
            print("Error receiving server messages:", e)
            break

def audio_sender(client, input_stream):
    global stop_audio_threads
    while not stop_audio_threads:
        try:
            data = input_stream.read(Chunks, exception_on_overflow=False)
            if data:
                client.send(data)
        except:
            break

def user_input_thread(client):
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

def audio_streaming(client):
    global stop_audio_threads, output_streams
    stop_audio_threads = False
    p = pyaudio.PyAudio()
    input_stream = p.open(format=Format,
                          channels=Channels,
                          rate=Rate,
                          input=True,
                          frames_per_buffer=Chunks)

    t_send = threading.Thread(target=audio_sender, args=(client, input_stream))
    t_recv = threading.Thread(target=parse_server_messages, args=(client,))
    t_input = threading.Thread(target=user_input_thread, args=(client,))

    t_send.start()
    t_recv.start()
    t_input.start()

    t_send.join()
    t_recv.join()

    # Close output streams
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
        client, welcome_message = connect_to_server()
        print(welcome_message)
        joined = choose_room(client)
        if not joined:
            continue
        audio_streaming(client)

if __name__ == "__main__":
    main()


