import socket
import sys
import json
import asyncio
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

host = "54.93.170.220"
port = 5000

Format = None
Chunks = 4096
Channels = 1
Rate = 44100

def main():
    client = socket.socket()
    client.connect((host, port))
    welcome_message = client.recv(4096).decode('utf-8')
    print(welcome_message)

    while True:
        choice = input("Type an existing room name to join, 'NEW:<RoomName>' to create a new room, or 'q' to quit: ").strip()
        if choice.lower() == 'q':
            client.close()
            sys.exit(0)

        client.send(choice.encode('utf-8'))
        response = client.recv(4096).decode('utf-8')
        print(response)

        if "Joined room:" in response:
            break
        elif "Invalid" in response or "does not exist" in response or "No room chosen" in response:
            if "Disconnecting" in response:
                client.close()
                return
        elif "No rooms available" in response:
            pass

    # Odaya girdik, şimdi WebRTC offer oluştur
    pc = RTCPeerConnection()

    # Mikrofondan ses al
    player = MediaPlayer("default", format="pulse", options={"channels":"1"})
    for t in player.audio:
        pc.addTrack(t)

    async def run_webrtc():
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        # Offer'ı server'a gönder
        off = {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}
        client.send(json.dumps(off).encode('utf-8'))

        # Server'dan answer bekle
        data = client.recv(8192)
        answer = json.loads(data.decode('utf-8'))
        await pc.setRemoteDescription(RTCSessionDescription(answer["sdp"], answer["type"]))

    loop = asyncio.new_event_loop()
    fut = asyncio.run_coroutine_threadsafe(run_webrtc(), loop)
    threading.Thread(target=loop.run_forever, daemon=True).start()
    fut.result()

    @pc.on("track")
    def on_track(track):
        print("Received track:", track.kind)
        # Burada track'i hoparlöre verebilirsiniz.
        # aiortc ile gelen track'i oynatmak için MediaBlackhole veya custom player kullanılabilir.
        # Basitlik adına şu an direkt track'i işleme koymuyoruz.

    # Client artık WebRTC üzerinden ses alışverişinde.
    # 'leave' komutu girilene kadar bekleyelim.
    while True:
        command = sys.stdin.readline().strip().lower()
        if command == "leave":
            coro = pc.close()
            asyncio.run_coroutine_threadsafe(coro, loop)
            client.close()
            break

if __name__ == "__main__":
    main()
