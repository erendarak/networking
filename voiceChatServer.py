import socket
import threading
from gi.repository import Gst, GObject

Gst.init(None)

HOST = "0.0.0.0"
PORT = 5000

# rooms = { "roomName": { "clients": [conn, ...], "sources": {conn: appsrc}, "pipeline": Gst.Pipeline, "appsink": appsink } }

rooms = {}
lock = threading.Lock()

class VoiceChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        print(f"Server started on {self.host}:{self.port}")

    def start(self):
        while True:
            conn, addr = self.server.accept()
            print(f"Client connected from {addr}")
            t = threading.Thread(target=self.handle_new_connection, args=(conn,))
            t.start()

    def handle_new_connection(self, conn):
        try:
            # Oda listesini gönder
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
                with lock:
                    if new_room_name not in rooms:
                        # Oda oluştur ve pipeline kur
                        rooms[new_room_name] = {
                            "clients": [],
                            "sources": {},
                            "pipeline": None,
                            "appsink": None
                        }
                        self.setup_pipeline(new_room_name)
                room_choice = new_room_name

            with lock:
                if room_choice not in rooms:
                    if room_choice == "":
                        conn.send(b"No room chosen. Disconnecting.\n")
                    else:
                        msg = f"Room '{room_choice}' does not exist. Disconnecting.\n"
                        conn.send(msg.encode('utf-8'))
                    conn.close()
                    return

                # Odaya ekle
                rooms[room_choice]["clients"].append(conn)

            conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

            # Her yeni client için bir appsrc oluştur
            self.add_source_to_room(room_choice, conn)

            self.handle_client(conn, room_choice)

        except Exception as e:
            print("Error in handle_new_connection:", e)
            conn.close()

    def setup_pipeline(self, room_name):
        # GStreamer pipeline: appsrc*(N) -> audiomixer -> queue -> appsink
        pipeline = Gst.Pipeline.new(None)
        mixer = Gst.ElementFactory.make("audiomixer", "mixer")
        appsink = Gst.ElementFactory.make("appsink", "sink")
        appsink.set_property("emit-signals", True)
        appsink.set_property("sync", False)
        appsink.set_property("async", False)
        appsink.connect("new-sample", self.on_new_sample, room_name)

        queue = Gst.ElementFactory.make("queue", "queue")

        pipeline.add(mixer)
        pipeline.add(queue)
        pipeline.add(appsink)

        mixer.link(queue)
        queue.link(appsink)

        pipeline.set_state(Gst.State.PLAYING)

        rooms[room_name]["pipeline"] = pipeline
        rooms[room_name]["appsink"] = appsink

    def add_source_to_room(self, room_name, conn):
        # Her connection için bir appsrc oluştur
        # PCM, 16bit, 1 kanal, 44100 Hz varsayılıyor
        appsrc = Gst.ElementFactory.make("appsrc", None)
        appsrc.set_property("format", Gst.Format.TIME)
        appsrc.set_property("is-live", True)
        appsrc.set_property("block", False)
        # Caps: audio/x-raw, format=S16LE, channels=1, rate=44100
        caps = Gst.Caps.from_string("audio/x-raw,format=S16LE,channels=1,rate=44100,layout=interleaved")
        appsrc.set_property("caps", caps)

        pipeline = rooms[room_name]["pipeline"]
        mixer = pipeline.get_by_name("mixer")

        pipeline.add(appsrc)
        appsrc.link(mixer)
        appsrc.set_state(Gst.State.PLAYING)

        rooms[room_name]["sources"][conn] = appsrc

    def on_new_sample(self, appsink, room_name):
        # appsink’ten veri al ve tüm client’lara gönder
        sample = appsink.emit("pull-sample")
        buf = sample.get_buffer()
        success, mapinfo = buf.map(Gst.MapFlags.READ)
        if success:
            data = mapinfo.data
            buf.unmap(mapinfo)
            # Mikslenmiş veriyi odadaki tüm client’lara gönder
            with lock:
                for cl in rooms[room_name]["clients"]:
                    try:
                        cl.sendall(data)
                    except:
                        pass
        return Gst.FlowReturn.OK

    def handle_client(self, conn, room_name):
        # Client’tan gelen ses verisini ilgili appsrc’ye push et
        # Chunks = 4096 örnek, 16bit, 2 bayt * 4096 = 8192 bayt
        # Burada client 1024 veya 4096 vb. okuyabilir, client tarafıyla uyumlu olsun.
        try:
            src = rooms[room_name]["sources"][conn]
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                # Gelen veriyi appsrc’ye push buffer
                buf = Gst.Buffer.new_allocate(None, len(data), None)
                buf.fill(0, data)
                src.emit("push-buffer", buf)

        except Exception as e:
            print("Error or disconnection:", e)
        finally:
            # Client ayrılıyor
            with lock:
                if conn in rooms[room_name]["clients"]:
                    rooms[room_name]["clients"].remove(conn)
                if conn in rooms[room_name]["sources"]:
                    # Kaynağı pipeline’dan çıkar
                    src = rooms[room_name]["sources"][conn]
                    src.emit("end-of-stream")
                    src.set_state(Gst.State.NULL)
                    pipeline = rooms[room_name]["pipeline"]
                    pipeline.remove(src)
                    del rooms[room_name]["sources"][conn]

                conn.close()
                if len(rooms[room_name]["clients"]) == 0:
                    # Oda boşaldı, pipeline durdur
                    pipeline = rooms[room_name]["pipeline"]
                    pipeline.set_state(Gst.State.NULL)
                    del rooms[room_name]

            print(f"Client disconnected from room {room_name}")


if __name__ == "__main__":
    server = VoiceChatServer(HOST, PORT)
    server.start()
