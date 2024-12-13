using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;
using MRLamb.StringUtils;

    class Server
    {
        private List<Client> Listeners = new List<Client>();
        private Dictionary<string, List<Client>> Rooms = new Dictionary<string, List<Client>>();
        private byte[] buffer = new byte[256];

        static void Main(string[] args)
        {
            Server diceServer = new Server();
            diceServer.Start();
        }

        private void Start()
        {
            string hostName = Dns.GetHostName();
            IPHostEntry ipEntry = Dns.GetHostEntry(hostName);
            IPAddress[] localAddress = ipEntry.AddressList;

            Socket listener = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
            listener.Bind(new IPEndPoint(Array.Find(localAddress, a => a.AddressFamily == AddressFamily.InterNetwork), 11000));
            listener.Listen(100);
            Console.WriteLine("IP Address: {0}", hostName);

            Console.WriteLine("Server started. Awaiting connections...");

            listener.BeginAccept(new AsyncCallback(OnConnectCallback), listener);
            Console.WriteLine("Enter LIST to view connections, ROOMS to view rooms, or EXIT to exit.");
            do
            {
                string command = Console.ReadLine();
                if (command.Equals("LIST"))
                {
                    foreach (Client client in Listeners)
                    {
                        Console.WriteLine(client.Identity);
                    }
                }
                else if (command.Equals("ROOMS"))
                {
                    foreach (var room in Rooms)
                    {
                        Console.WriteLine($"Room: {room.Key}, Clients: {room.Value.Count}");
                    }
                }
                else if (command.Equals("EXIT"))
                {
                    break;
                }

            } while (true);
        }

        private void OnConnectCallback(IAsyncResult ar)
        {
            Socket listener = (Socket)ar.AsyncState;
            Socket socket = listener.EndAccept(ar);
            Client client = new Client(socket);

            Listeners.Add(client);
            Console.WriteLine("Client connected on {0}", client.Socket.RemoteEndPoint);
            WaitForData(client.Socket);

            string request = "IDENTIFY";
            client.Socket.Send(Encoding.ASCII.GetBytes(request));

            listener.BeginAccept(new AsyncCallback(OnConnectCallback), listener);
        }

        private void WaitForData(Socket socket)
        {
            if (socket.Connected)
            {
                AsyncCallback receiveData = new AsyncCallback(OnReceive);
                socket.BeginReceive(buffer, 0, buffer.Length, SocketFlags.None, receiveData, socket);
            }
        }

        private void OnReceive(IAsyncResult ar)
        {
            Socket socket = (Socket)ar.AsyncState;
            Client client = Listeners.Find(a => a.Socket.Equals(socket));
            try
            {
                int bytesRec = socket.EndReceive(ar);
                if (bytesRec > 0)
                {
                    string message = Encoding.ASCII.GetString(buffer, 0, bytesRec);

                    if (message.StartsWith("JOIN:"))
                    {
                        string roomName = message.Substring(5).Trim();
                        if (!Rooms.ContainsKey(roomName))
                        {
                            Rooms[roomName] = new List<Client>();
                        }
                        Rooms[roomName].Add(client);
                        client.Room = roomName;
                        Console.WriteLine($"Client joined room: {roomName}");
                    }
                    else if (message.StartsWith("MESSAGE:"))
                    {
                        string roomMessage = message.Substring(8).Trim();
                        Propagate(roomMessage, client);
                    }
                    else if (message.StartsWith("IDENTITY:"))
                    {
                        client.Identity = message.Substring(9).Trim();
                        Console.WriteLine($"Client identified as: {client.Identity}");
                    }

                    AsyncCallback receiveData = new AsyncCallback(OnReceive);
                    socket.BeginReceive(buffer, 0, buffer.Length, SocketFlags.None, receiveData, socket);
                }
            }
            catch (SocketException ex)
            {
                Console.WriteLine("Client disconnected: {0}", ex.Message);
                if (client.Room != null && Rooms.ContainsKey(client.Room))
                {
                    Rooms[client.Room].Remove(client);
                }
                Listeners.Remove(client);
            }
        }

        private void Propagate(string message, Client sender)
        {
            if (sender.Room != null && Rooms.ContainsKey(sender.Room))
            {
                foreach (Client client in Rooms[sender.Room])
                {
                    if (client != sender && client.Socket.Connected)
                    {
                        client.Socket.Send(Encoding.ASCII.GetBytes(message));
                    }
                }
            }
        }
    }

