from pathlib import Path

import asyncio
from aiohttp import web

from .messages import ClientStatusMsg, QuitMsg


class AsyncServer:
    def __init__(self, command_queue, response_queue):
        self.command_queue = command_queue
        self.response_queue = response_queue

        done_template_file = Path(__file__).parent / 'index.html'
        with done_template_file.open('rt') as f:
            self.form_template = f.read()

        self.client_sockets = {}

    async def handle_get(self, request):
        return web.Response(text=self.form_template, content_type='text/html')

    async def start_client(self, request):
        self.response_queue.put(ClientStatusMsg(request.remote, 'new'))
        return web.Response(text='ok')

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        self.client_sockets[request.remote] = ws
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                await ws.send_str(f"Received: {msg.data}")
            elif msg.type == web.WSMsgType.BINARY:
                await ws.send_bytes(msg.data)
            elif msg.type == web.WSMsgType.CLOSE:
                break
            elif msg.type == web.WSMsgType.PING:
                await ws.pong()
            elif msg.type == web.WSMsgType.PONG:
                pass

        return ws

    async def check_queue(self):
        while True:
            if self.command_queue.empty():
                await asyncio.sleep(1)
                continue

            data = self.command_queue.get()
            if isinstance(data, QuitMsg):
                await self.site.stop()
                break
            elif isinstance(data, ClientStatusMsg):
                if data.status == 'started':
                    await self.client_sockets[data.host].send_str('stream-started')
            else:
                print(f"Unknown command: {data}")

    async def start_server(self):
        app = web.Application()
        app.router.add_get('/', self.handle_get)
        app.router.add_post('/play', self.start_client)
        app.router.add_get('/ws', self.handle_websocket)

        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '0.0.0.0', 8080)
        await self.site.start()

    async def run(self):
        await asyncio.gather(self.start_server(), self.check_queue())


def run_server(command_queue, response_queue):
    server = AsyncServer(command_queue, response_queue)
    asyncio.run(server.run())
