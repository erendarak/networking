using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

    class Client
    {
        private Socket clientSocket;
        private string serverIp = "63.177.85.93"; // Change to your server's IP
        private int serverPort = 5000;
        private bool isRunning = true;

        static void Main(string[] args)
        {
            Client client = new Client();
            client.Start();
        }

        private void Start()
        {
            try
            {
                clientSocket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                clientSocket.Connect(new IPEndPoint(IPAddress.Parse(serverIp), serverPort));

                Console.WriteLine("Connected to server.");

                Thread receiveThread = new Thread(ReceiveMessages);
                receiveThread.Start();

                while (isRunning)
                {
                    Console.WriteLine("Enter command: IDENTIFY:<name>, JOIN:<room>, MESSAGE:<message>, or EXIT");
                    string command = Console.ReadLine();

                    if (command.Equals("EXIT"))
                    {
                        isRunning = false;
                        clientSocket.Shutdown(SocketShutdown.Both);
                        clientSocket.Close();
                        break;
                    }

                    SendMessage(command);
                }

                receiveThread.Join();
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error: " + ex.Message);
            }
        }

        private void SendMessage(string message)
        {
            try
            {
                byte[] data = Encoding.ASCII.GetBytes(message);
                clientSocket.Send(data);
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error sending message: " + ex.Message);
            }
        }

        private void ReceiveMessages()
        {
            try
            {
                while (isRunning)
                {
                    byte[] buffer = new byte[1024];
                    int bytesRead = clientSocket.Receive(buffer);
                    if (bytesRead > 0)
                    {
                        string message = Encoding.ASCII.GetString(buffer, 0, bytesRead);
                        Console.WriteLine("Server: " + message);
                    }
                }
            }
            catch (SocketException ex)
            {
                Console.WriteLine("Disconnected from server: " + ex.Message);
                isRunning = false;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error receiving message: " + ex.Message);
            }
        }
    }

