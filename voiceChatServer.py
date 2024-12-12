import socket
import threading
import queue
import struct
import time

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

# Odaları tutan sözlük.
# Her oda için:
# {
#   'clients': [conn1, conn2, ...],
#   'queues': {conn1: Queue(), ...},
#   'mixing_thread': threading.Thread veya None,
#   'stop_mixing': bool
# }
rooms = {}

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
            # Miksleme thread'i bu veriyi alıp işleyip diğerlerine dağıtacak
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
                # Oda dict'ini thread durduktan sonra silelim
                # Thread durmadan silersek sorun olabilir.
                # Basitçe biraz bekleyelim:
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

        # Tüm client'lardan CHUNK uzunluğunda veri çek
        buffers = []
        # Eğer client'ta veri yoksa sessizlik ekle
        for cl in clients:
            q = room_info['queues'][cl]
            if not q.empty():
                buf = q.get()
                # Eğer buf CHUNK'tan farklı uzunluktaysa, kısalt veya doldur
                if len(buf) < CHUNK * SAMPLE_WIDTH:
                    buf += bytes([0] * ((CHUNK * SAMPLE_WIDTH) - len(buf)))
                buffers.append(buf)
            else:
                # Sessiz chunk
                buffers.append(bytes([0] * (CHUNK * SAMPLE_WIDTH)))

        # Eğer kimse konuşmuyorsa sadece beklemeye devam et
        # Ama yine de sessizlikte de olsa gönderirsek sorun olmaz,
        # fakat gereksiz bant genişliği harcar.
        # İsterseniz kimse konuşmuyorsa göndermeyebilirsiniz.

        # buffers içinde her client'in 4096 sample (2 byte per sample) verisi var
        # Bu verileri mix edelim
        # 16-bit little-endian signed integers
        samples_list = []
        for buf in buffers:
            samples = struct.unpack('<' + ('h' * CHUNK), buf)
            samples_list.append(samples)

        mixed_samples = []
        for i in range(CHUNK):
            s_sum = 0
            for s in samples_list:
                s_sum += s[i]
            # Clamping
            if s_sum > 32767:
                s_sum = 32767
            elif s_sum < -32768:
                s_sum = -32768
            mixed_samples.append(s_sum)

        mixed_data = struct.pack('<' + ('h' * CHUNK), *mixed_samples)

        # Şimdi bu mixed_data'yı odadaki tüm client'lara gönder
        for cl in clients:
            try:
                cl.send(mixed_data)
            except:
                pass

        # Çok yoğun işlem yapmamak için ufak bir bekleme, idealde gerekli olmayabilir
        # ancak yüksek CPU kullanımı görürseniz azaltabilirsiniz.
        # Aslında ses gerçek zamanlı olduğu için bekleme koymuyoruz.
        # time.sleep(0.001)

    # Oda ya silindi ya da stop_mixing true oldu
    # Thread bitiyor
    print(f"Mixing thread for room {room_name} stopped.")


start()
