import asyncio
import websockets
import json

clients = set()

async def handler(websocket, path):
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

if __name__ == "__main__":
    start_server = websockets.serve(handler, "0.0.0.0", 5000)
    print("WebRTC signaling server running on ws://0.0.0.0:5000")

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
