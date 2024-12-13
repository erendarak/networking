import asyncio
import websockets
import json

clients = set()

async def handler(websocket):
    # Add the client to the set
    clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            # Relay messages to other clients
            for client in clients:
                if client != websocket:
                    await client.send(json.dumps(data))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # Remove the client on disconnect
        clients.remove(websocket)

async def main():
    print("WebRTC signaling server running on ws://0.0.0.0:5000")
    async with websockets.serve(handler, "0.0.0.0", 5000):
        await asyncio.Future()  # Keep the server running forever

if __name__ == "__main__":
    asyncio.run(main())
