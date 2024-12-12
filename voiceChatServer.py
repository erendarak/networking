import socket
import threading
import asyncio
import sys
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaBlackhole, MediaRelay
from aiortc.contrib.media import MediaStreamTrack

port = 5000
host = "0.0.0.0"

server = socket.socket()
server.bind((host, port))
server.listen(5)

rooms = {}  # "roomName": { "peers": [ (pc, conn), ... ], "relay": MediaRelay() }

# aiortc event loop
loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=loop.run_forever, daemon=True)
asyncio_thread.start()

def start():
    print("Server started, waiting for connections...")
    while True:
        conn, addr = server.accept()
        print(f"Client connected from {addr}")
        t = threading.Thread(target=handle_new_connection, args=(conn,))
        t.start()

def handle_new_connection(conn):
    try:
        # Oda listesini gönder
        room_list = "\n".join(rooms.keys()) if rooms else "No rooms available."
        welcome_msg = (
                "Available rooms:\n" +
                room_list +
                "\n\nType an existing room name to join it, or type 'NEW:<RoomName>' to create a new room:\n"
        )
        conn.send(welcome_msg.encode('utf-8'))

        # Oda seçimi
        room_choice = conn.recv(1024).decode('utf-8').strip()
        if room_choice.startswith("NEW:"):
            new_room_name = room_choice.split("NEW:")[-1].strip()
            if not new_room_name:
                conn.send(b"Invalid room name. Disconnecting.\n")
                conn.close()
                return
            if new_room_name not in rooms:
                rooms[new_room_name] = {"peers": [], "relay": MediaRelay()}
            room_choice = new_room_name

        if room_choice not in rooms:
            if room_choice == "":
                conn.send(b"No room chosen. Disconnecting.\n")
            else:
                conn.send(f"Room '{room_choice}' does not exist. Disconnecting.\n".encode('utf-8'))
            conn.close()
            return

        conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

        # Oda içi WebRTC bağlantısını başlat
        # Client offer bekle
        data = conn.recv(4096)
        # data JSON formatında: {"type": "offer", "sdp": "..."}
        offer = json.loads(data.decode('utf-8'))
        if offer["type"] != "offer":
            conn.close()
            return

        # RTCPeerConnection oluştur
        pc = RTCPeerConnection()

        # Odaya ekle
        room = rooms[room_choice]

        # Diğer peer'ların tracklerini bu peer'e ekle
        for (other_pc, other_conn) in room["peers"]:
            # Her existing pc’nin tracklerini buna ekle
            # On_track eventinde eklenecek
            pass

        # Yeni PC’nin track event’i
        @pc.on("track")
        def on_track(track):
            # Gelen track’i relay et
            relay_track = room["relay"].subscribe(track)
            # Bu track'i odadaki diğer peer'lere ekle
            # (Her yeni track geldiğinde diğer peer'lere forward ediyoruz)
            for (other_pc, other_conn) in room["peers"]:
                other_pc.addTrack(relay_track)

            # Aynı şekilde bu yeni pc'ye de odadaki eski trackleri eklememiz lazım.
            # Ama eski trackler zaten @other_pc.on("track") ile ekleniyor.
            # Burada basit tutuyoruz.

        async def handle_webrtc():
            # Offer alındı, setRemoteDescription
            await pc.setRemoteDescription(RTCSessionDescription(offer["sdp"], offer["type"]))

            # Answer oluştur
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # Answer'ı client'a gönder
            ans = {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}
            ans_data = json.dumps(ans).encode('utf-8')
            conn.send(ans_data)

            # Odaya ekle
            room["peers"].append((pc, conn))

        fut = asyncio.run_coroutine_threadsafe(handle_webrtc(), loop)
        fut.result()

        # Artık WebRTC üzerinden ses akışı sağlanacak.
        # Bu thread şimdilik burada kalabilir,
        # Peer kapandığında pc kapatılır.

        # Client disconnect olana kadar bekle
        # WebRTC bağlantısı kesilince, peer'i odadan çıkar
        while True:
            # Burada normal bir bekleme yapıyoruz.
            # Gerçekte peer connection kapandığında bir event yakalayıp odadan çıkarabilirsin.
            # Şimdilik soket kapanınca çıkıyoruz.
            chunk = conn.recv(1024)
            if not chunk:
                break

    except Exception as e:
        print("Error in handle_new_connection:", e)
    finally:
        # Client ayrılıyor
        # PC kapat
        for (p, c) in rooms[room_choice]["peers"]:
            if c == conn:
                coro = p.close()
                asyncio.run_coroutine_threadsafe(coro, loop)
                rooms[room_choice]["peers"].remove((p, c))
                break
        conn.close()
        if len(rooms[room_choice]["peers"]) == 0:
            del rooms[room_choice]
        print(f"Client disconnected from room {room_choice}")

start()
