import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

class VoiceChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        print(f"Server started, listening on {self.host}:{self.port}")

        # Oda yönetimi
        self.rooms = {}  # { "roomName": [conn1, conn2, ...] }

    def start(self):
        while True:
            conn, addr = self.server.accept()
            print(f"Client connected from {addr}")
            t = threading.Thread(target=self.handle_new_connection, args=(conn,))
            t.start()

    def handle_new_connection(self, conn):
        try:
            # Oda listesini gönder
            room_list = "\n".join(self.rooms.keys()) if self.rooms else "No rooms available."
            welcome_msg = (
                "Available rooms:\n" +
                room_list +
                "\n\nType an existing room name to join it, or type 'NEW:<RoomName>' to create a new room:\n"
            )

            conn.send(welcome_msg.encode('utf-8'))

            # Oda seçimini al
            room_choice = conn.recv(1024)
            if not room_choice:
                conn.close()
                return
            room_choice = room_choice.decode('utf-8').strip()

            # Yeni oda yaratma
            if room_choice.startswith("NEW:"):
                new_room_name = room_choice.split("NEW:")[-1].strip()
                if not new_room_name:
                    conn.send(b"Invalid room name. Disconnecting.\n")
                    conn.close()
                    return

                if new_room_name not in self.rooms:
                    self.rooms[new_room_name] = []
                room_choice = new_room_name

            # Oda var mı kontrolü
            if room_choice not in self.rooms:
                if room_choice == "":
                    conn.send(b"No room chosen. Disconnecting.\n")
                else:
                    msg = f"Room '{room_choice}' does not exist. Disconnecting.\n"
                    conn.send(msg.encode('utf-8'))
                conn.close()
                return

            # Odaya ekle
            self.rooms[room_choice].append(conn)
            conn.send(f"Joined room: {room_choice}\n".encode('utf-8'))

            self.handle_client(conn, room_choice)

        except Exception as e:
            print("Error in handle_new_connection:", e)
            conn.close()

    def handle_client(self, conn, room_name):
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                # Bu odadaki diğer client'lara ilet
                for cl in self.rooms[room_name]:
                    if cl != conn:
                        cl.send(data)
        except Exception as e:
            print("Error or disconnection:", e)
        finally:
            # Odadan çıkar
            if conn in self.rooms[room_name]:
                self.rooms[room_name].remove(conn)
            conn.close()
            # Oda boşsa sil
            if len(self.rooms[room_name]) == 0:
                del self.rooms[room_name]
            print(f"Client disconnected from room {room_name}")


if __name__ == "__main__":
    server = VoiceChatServer(HOST, PORT)
    server.start()
