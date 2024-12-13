import socket
import threading
import pyaudio
import sys

host = "54.93.170.220"  # Sunucunun IP'si
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
            if "Disconnecting" in response:
                client.close()
                return False
        elif "No rooms available" in response:
            pass

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
                client.sendall(data)
            except:
                break

    def receive_audio():
        while not stop_audio_threads:
            try:
                data = client.recv(8192) # 4096 örnek *2 bayt = 8192,
                                         # sunucu miksleyip appsink'ten tam chunk alır.
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

    input_stream.stop_stream()
    input_stream.close()
    output_stream.stop_stream()
    output_stream.close()
    p.terminate()

def main():
    client, welcome_message = connect_to_server()
    print(welcome_message)

    joined = choose_room(client)
    if not joined:
        return

    audio_streaming(client)

if __name__ == "__main__":
    main()
