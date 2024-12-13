import asyncio
import websockets
import json

clients = {}

async def handler(websocket):
    # Assign a unique ID to each client
    client_id = id(websocket)
    clients[client_id] = websocket
    print(f"Client connected: {client_id}")

    try:
        async for message in websocket:
            data = json.loads(message)

            # Relay messages to the intended recipient or broadcast to all
            if "to" in data:  # Send to a specific client
                recipient_id = data["to"]
                if recipient_id in clients:
                    await clients[recipient_id].send(json.dumps(data))
            else:  # Broadcast to all except the sender
                for other_client_id, other_client_socket in clients.items():
                    if other_client_id != client_id:
                        await other_client_socket.send(json.dumps(data))

    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {client_id}")

    finally:
        del clients[client_id]

async def main():
    print("WebRTC signaling server running on ws://0.0.0.0:5000")
    async with websockets.serve(handler, "0.0.0.0", 5000):
        await asyncio.Future()  # Keep the server running forever

if __name__ == "__main__":
    asyncio.run(main())
