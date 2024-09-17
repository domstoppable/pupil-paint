from pathlib import Path

import asyncio
from aiohttp import web

from .messages import ClientIdentifyMsg, QuitMsg


class AsyncServer:
    def __init__(self, command_queue, response_queue):
        self.command_queue = command_queue
        self.response_queue = response_queue

        done_template_file = Path(__file__).parent / 'index.html'
        with done_template_file.open('rt') as f:
            self.form_template = f.read()

    async def handle_get(self, request):
        return web.Response(text=self.form_template, content_type='text/html')

    async def start_client(self, request):
        self.response_queue.put(ClientIdentifyMsg(request.remote))
        return web.Response(text='ok')

    async def check_queue(self):
        while True:
            if self.command_queue.empty():
                await asyncio.sleep(1)
                continue

            data = self.command_queue.get()
            if isinstance(data, QuitMsg):
                await self.site.stop()
                break
            else:
                print(f"Unknown command: {data}")

    async def start_server(self):
        app = web.Application()
        app.router.add_get('/', self.handle_get)
        app.router.add_post('/play', self.start_client)

        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, '0.0.0.0', 8080)
        await self.site.start()

    async def run(self):
        await asyncio.gather(self.start_server(), self.check_queue())


def run_server(command_queue, response_queue):
    server = AsyncServer(command_queue, response_queue)
    asyncio.run(server.run())
