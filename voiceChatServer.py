import socket
import threading
import queue
import struct
import time

port = 5000
host = "0.0.0.0"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen(5)

# Odalar için yapı
rooms = {}  # { "RoomName": { "clients": [], "queues": {conn:Queue}, "mixing_thread":Thread, "stop_mixing":False } }

CHUNK = 4096
SAMPLE_WIDTH = 2  # 16-bit ses
CHANNELS = 1
RATE = 44100


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
                    'clients': [],
                    'queues': {},
                    'mixing_thread': None,
                    'stop_mixing': False
                }
            room_choice = new_room_name

        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        # Odaya client ekle
        rooms[room_choice]['clients'].append(conn)
        rooms[room_choice]['queues'][conn] = queue.Queue()

        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        # Eğer miksleme thread'i yoksa başlat
        if rooms[room_choice]['mixing_thread'] is None:
            rooms[room_choice]['stop_mixing'] = False
            mt = threading.Thread(target=mixing_thread, args=(room_choice,), daemon=True)
            rooms[room_choice]['mixing_thread'] = mt
            mt.start()

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
            # Gelen veriyi ilgili client's queue'suna ekle
            if room_name in rooms and conn in rooms[room_name]['queues']:
                rooms[room_name]['queues'][conn].put(data)
    except Exception as e:
        print("Error or disconnection:", e)
    finally:
        # Client odayı terk ediyor
        if room_name in rooms:
            if conn in rooms[room_name]['clients']:
                rooms[room_name]['clients'].remove(conn)
            if conn in rooms[room_name]['queues']:
                del rooms[room_name]['queues'][conn]

            conn.close()

            # Oda boşaldıysa odayı sil
            if len(rooms[room_name]['clients']) == 0:
                rooms[room_name]['stop_mixing'] = True
                # mixing_thread kendi kendine duracak
                time.sleep(0.5)
                if room_name in rooms:
                    del rooms[room_name]

            print(f"Client disconnected from room {room_name}")


def mixing_thread(room_name):
    # Bu thread oda boşalana kadar çalışır
    while True:
        if room_name not in rooms:
            break
        if rooms[room_name]['stop_mixing']:
            break

        room_info = rooms[room_name]
        clients = room_info['clients']
        if len(clients) == 0:
            time.sleep(0.1)
            continue

        # Her client'tan veri çek (veya sessizlik)
        buffers = []
        # Bu listede her index bir client'a karşılık geliyor
        for cl in clients:
            q = room_info['queues'][cl]
            if not q.empty():
                buf = q.get()
                if len(buf) < CHUNK * SAMPLE_WIDTH:
                    buf += bytes((CHUNK * SAMPLE_WIDTH) - len(buf))
                buffers.append(buf)
            else:
                # Sessiz chunk
                buffers.append(bytes([0] * (CHUNK * SAMPLE_WIDTH)))

        # Bütün buffer'ları integer sample array'e çevir
        samples_list = []
        for buf in buffers:
            samples = struct.unpack('<' + ('h' * CHUNK), buf)
            samples_list.append(samples)

        # Global miks: tüm clientların sesini topla
        global_mix = [0] * CHUNK
        for i in range(CHUNK):
            s_sum = 0
            for s in samples_list:
                s_sum += s[i]
            # Clamping
            if s_sum > 32767:
                s_sum = 32767
            elif s_sum < -32768:
                s_sum = -32768
            global_mix[i] = s_sum

        # Şimdi her client için kendi sesini global_mix'ten çıkar
        # final_for_client = global_mix - self_samples
        # Bu sayede client kendi sesini duymayacak.
        for idx, cl in enumerate(clients):
            client_samples = samples_list[idx]
            final_samples = []
            for i in range(CHUNK):
                s_final = global_mix[i] - client_samples[i]
                # Yine clamping yapalım
                if s_final > 32767:
                    s_final = 32767
                elif s_final < -32768:
                    s_final = -32768
                final_samples.append(s_final)

            final_data = struct.pack('<' + ('h' * CHUNK), *final_samples)
            try:
                cl.send(final_data)
            except:
                pass

    print(f"Mixing thread for room {room_name} stopped.")


start()
