import socket
import threading
import struct
import time

port = 5000
host = "0.0.0.0"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen(5)

rooms = {}  # { roomName: {"clients": [], "active_speaker": None, "silence_count": {conn: int}} }

CHUNK = 4096
SAMPLE_WIDTH = 2  # 16-bit PCM
CHANNELS = 1
RATE = 44100

SILENCE_THRESHOLD = 50  # Max ortalama mutlak değer (çok küçük bir seviye) sessizlik için
SILENCE_RESET_COUNT = 50  # Aktif konuşmacı bu kadar üst üste sessiz chunk gönderirse aktifliğini kaybeder

def start():
    print("Server started, waiting for connections...")
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        t = threading.Thread(target=handle_new_connection, args=(conn,))
        t.start()

def handle_new_connection(conn):
    try:
        room_list = "\n".join(rooms.keys()) if rooms else "No rooms available."
        welcome_msg = (
            "Available rooms:\n" +
            room_list +
            "\n\nType an existing room name to join it, or type 'NEW:<RoomName>' to create a new room:\n"
        )
        conn.send(welcome_msg.encode('utf-8'))

        room_choice = conn.recv(1024)
        if not room_choice:
            conn.close()
            return
        room_choice = room_choice.decode('utf-8').strip()

        if room_choice.startswith("NEW:"):
            new_room_name = room_choice.split("NEW:")[-1].strip()
            if not new_room_name:
                conn.send(b"Invalid room name. Disconnecting.\n")
                conn.close()
                return
            if new_room_name not in rooms:
                rooms[new_room_name] = {
                    "clients": [],
                    "active_speaker": None,
                    "silence_count": {}
                }
            room_choice = new_room_name

        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        rooms[room_choice]["clients"].append(conn)
        rooms[room_choice]["silence_count"][conn] = 0
        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        handle_client(conn, room_choice)

    except Exception as e:
        print("Error in handle_new_connection:", e)
        conn.close()

def handle_client(conn, room_name):
    try:
        while True:
            data = conn.recv(CHUNK)
            if not data:
                break

            # Ses analizi
            volume = average_absolute_amplitude(data)
            room = rooms.get(room_name)
            if room is None:
                break

            # Aktif konuşmacı yoksa ve sesli chunk geldiyse bu client aktif konuşmacı olsun
            if room["active_speaker"] is None and volume > SILENCE_THRESHOLD:
                room["active_speaker"] = conn
                room["silence_count"][conn] = 0

            # Eğer bu client aktif konuşmacı ise herkese yolla
            if room["active_speaker"] == conn:
                # Eğer sessizlik ise sayacı artır, değilse sıfırla
                if volume <= SILENCE_THRESHOLD:
                    room["silence_count"][conn] += 1
                else:
                    room["silence_count"][conn] = 0

                # Eğer belli sayıda sessizlikten sonra aktif konuşmacı sessizliğe gömüldüyse aktifliği sıfırla
                if room["silence_count"][conn] > SILENCE_RESET_COUNT:
                    room["active_speaker"] = None
                else:
                    # Aktif konuşmacı ses gönderiyor, herkese dağıt
                    for cl in room["clients"]:
                        if cl != conn:
                            try:
                                cl.send(data)
                            except:
                                pass
            else:
                # Bu client aktif konuşmacı değilse sesi göz ardı et
                # (Bu sayede aynı anda iki kişinin sesi karışmaz)
                pass

    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Client disconnect
        cleanup_client(conn, room_name)

def cleanup_client(conn, room_name):
    if room_name in rooms:
        room = rooms[room_name]
        if conn in room["clients"]:
            room["clients"].remove(conn)
        if conn in room["silence_count"]:
            del room["silence_count"][conn]
        # Eğer bu client aktif konuşmacı ise aktifliği sıfırla
        if room["active_speaker"] == conn:
            room["active_speaker"] = None
        conn.close()
        print(f"Client disconnected from room {room_name}")
        # Oda boş ise odayı sil
        if len(room["clients"]) == 0:
            del rooms[room_name]

def average_absolute_amplitude(data):
    # 16-bit signed data
    # data uzunluğumuz CHUNK * 2 byte
    samples = struct.unpack('<' + ('h' * (len(data)//2)), data)
    abs_values = [abs(s) for s in samples]
    avg = sum(abs_values) / len(abs_values)
    return avg

start()
