import multiprocessing as mp
from multiprocessing import shared_memory
import random
from pathlib import Path
import time

import pygame
import numpy as np

from . import bgscore
from .server import run_server
from .client import get_surface_gazes
from .local_ip import get_local_ip
from .messages import (
    QuitMsg,
    ClientStatusMsg,
    GazePointMsg,
    SwatchesMsg,
    DrawMsg,
    CalculateScoreMsg,
)
from .image_helpers import make_marker, make_qr


class ClientMeta:
    marker_verts = None
    screen_size = None

    colors = [
        (255, 0, 0),      # Red
        (0, 255, 0),      # Green
        (0, 0, 255),      # Blue
        (255, 255, 0),    # Yellow
        (255, 165, 0),    # Orange
        (128, 0, 128),    # Purple
        (0, 255, 255),    # Cyan
        (255, 192, 203),  # Pink
    ]

    def __init__(self, host, data_queue, color=None):
        if color is not None:
            color = tuple(color)

        self.host = host
        self.color = color
        self.command_queue = mp.Queue()
        self.data_queue = data_queue
        self.last_gaze = None
        self.last_gaze_time = None
        self.enabled = False

        self.process = mp.Process(
            target=get_surface_gazes,
            args=(
                host,
                ClientMeta.marker_verts,
                ClientMeta.screen_size,
                self.command_queue,
                data_queue
            )
        )


class PupilPainter:
    def __init__(self):
        self.client_info_queue = mp.Queue()
        self.server_command_queue = mp.Queue()
        self.gaze_data_queue = mp.Queue()
        self.score_trigger_queue = mp.Queue()
        self.new_score_queue = mp.Queue()

        self.server_proc = mp.Process(target=run_server, args=(self.server_command_queue, self.client_info_queue))
        self.score_proc = None

        self.tag_size = 200
        self.scoreboard = {}

    def run(self):
        pygame.init()
        self.server_proc.start()

        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        #self.screen = pygame.display.set_mode((1920, 1080))
        self.screen_width, self.screen_height = self.screen.get_size()

        self.font = pygame.font.SysFont('monospace', 32)
        self.font.bold = True

        tag_size_no_margin = self.tag_size * 0.8
        self.canvas_rect = pygame.Rect(
            self.tag_size + 5,
            self.tag_size / 2,
            self.screen_width - self.tag_size * 1.5,
            self.screen_height - self.tag_size,
        )

        markers = [make_marker(mid, self.tag_size) for mid in range(5)]
        marker_margin = self.tag_size / 10
        marker_verts = {}
        marker_corners = [
            [0, 0],
            [(self.screen_width - self.tag_size) / 2, 0],
            [self.screen_width - self.tag_size, 0],
            [self.screen_width - self.tag_size, self.screen_height - self.tag_size],
            [0, self.screen_height - self.tag_size],
        ]

        for idx, mc in enumerate(marker_corners):
            tl = [
                marker_corners[idx][0] + marker_margin,
                marker_corners[idx][1] + marker_margin
            ]
            br = [
                tl[0] + tag_size_no_margin,
                tl[1] + tag_size_no_margin
            ]
            marker_verts[idx] = [
                tl,
                [br[0], tl[1]],
                br,
                [tl[0], br[1]]
            ]

        ClientMeta.marker_verts = marker_verts
        ClientMeta.screen_size = [self.screen_width, self.screen_height]

        qr_image = make_qr(f"http://{get_local_ip()}:8080/", self.tag_size)

        pygame.display.set_caption("Pupil Painter")

        brush_path = Path(__file__).parent / "brush.png"
        self.brush_image = pygame.image.load(brush_path).convert_alpha()

        # Create the canvas surface
        canvas_size = (self.canvas_rect.width, self.canvas_rect.height)
        self.canvas = pygame.Surface(canvas_size)
        self.canvas.fill((0, 0, 0))

        self.shared_canvas_data = shared_memory.SharedMemory(
            create=True,
            size=np.dtype(np.uint8).itemsize * (canvas_size[0] * canvas_size[1] * 3),
        )
        self.shared_canvas_as_np = np.ndarray(shape=(*canvas_size, 3), dtype=np.uint8, buffer=self.shared_canvas_data.buf).reshape(-1, 3)

        self.score_proc = mp.Process(
            target=bgscore.keep_score,
            args=(*canvas_size, self.shared_canvas_data.name, self.score_trigger_queue, self.new_score_queue)
        )
        self.score_proc.start()

        # Clock to control frame rate
        clock = pygame.time.Clock()

        self.clients = {}

        self.server_command_queue.put(SwatchesMsg(ClientMeta.colors))

        self.running = True
        while self.running:
            self.iteration_start_time = time.time()

            self.check_for_events()
            if not self.running:
                break

            self.check_for_new_clients()
            self.check_for_new_gazes()
            self.check_for_new_scores()

            # update display
            self.screen.fill((0, 0, 0))

            # paint the updated canvas to the screen
            self.screen.fill((128, 128, 128), self.canvas_rect.inflate(10, 10))
            self.screen.blit(self.canvas, (self.canvas_rect.x, self.canvas_rect.y))

            # paint the scoreboard
            self.draw_scoreboard()

            # paint user crosshairs
            for client in self.clients.values():
                if client.last_gaze is None or self.iteration_start_time - client.last_gaze_time > 1.0:
                    continue

                pygame.draw.circle(self.screen, (255, 255, 255), client.last_gaze, 21, 7)
                pygame.draw.circle(self.screen, client.color or (200, 200, 200), client.last_gaze, 20, 5)

            # paint the markers
            self.screen.blit(markers[0], (0, 0))
            self.screen.blit(markers[1], ((self.screen_width - self.tag_size) / 2, 0))
            self.screen.blit(markers[2], (self.screen_width - self.tag_size, 0))
            self.screen.blit(markers[3], (self.screen_width - self.tag_size, self.screen_height - self.tag_size))
            self.screen.blit(markers[4], (0, self.screen_height - self.tag_size))
            self.screen.blit(qr_image, ((self.screen_width - qr_image.get_size()[0]) / 2, self.screen_height - qr_image.get_size()[1]))

            fps_text = self.font.render(str(round(clock.get_fps())), True, (255, 255, 255))
            self.screen.blit(fps_text, (self.tag_size * 1.1, 0))

            pygame.display.flip()

            clock.tick(60)

    def check_for_events(self):
        for event in pygame.event.get():
            escape_released = event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE
            if event.type == pygame.QUIT or escape_released:
                self.cleanup()
                self.running = False

    def check_for_new_clients(self):
        while not self.client_info_queue.empty():
            message = self.client_info_queue.get()
            if isinstance(message, ClientStatusMsg):
                client_ip = message.host
                if message.status == 'new':
                    old_color = None
                    if client_ip in self.clients:
                        self.clients[client_ip].command_queue.put(QuitMsg())
                        old_color = self.clients[client_ip].color

                    client = ClientMeta(client_ip, self.gaze_data_queue, old_color)
                    client.process.start()

                    self.clients[client_ip] = client
                    print("Starting client", client_ip)

            elif isinstance(message, DrawMsg):
                client = self.clients[message.host]
                client.color = message.color
                client.enabled = message.enabled

    def check_for_new_gazes(self):
        while not self.gaze_data_queue.empty():
            data = self.gaze_data_queue.get()

            if isinstance(data, GazePointMsg):
                gaze_pos = data.x, data.y
                client_info = self.clients[data.host]
                client_info.last_gaze = gaze_pos
                client_info.last_gaze_time = self.iteration_start_time

                if not client_info.enabled or client_info.color is None:
                    pass

                else:
                    if self.canvas_rect.x <= gaze_pos[0] < self.canvas_rect.x + self.canvas_rect.width:
                        tinted_brush = self.brush_image.copy()
                        tinted_brush.fill(client_info.color, None, pygame.BLEND_MULT)
                        tinted_brush = pygame.transform.rotate(tinted_brush, random.uniform(0, 360))

                        brush_rect = tinted_brush.get_rect(center=(gaze_pos[0] - self.canvas_rect.x, gaze_pos[1] - self.canvas_rect.y))

                        # Copy the target portion of the canvas
                        target_area = pygame.Surface((brush_rect.width, brush_rect.height))
                        target_area.blit(self.canvas, (0, 0), brush_rect)

                        # Paint the brush on the canvas
                        self.canvas.blit(tinted_brush, brush_rect.topleft)

            elif isinstance(data, ClientStatusMsg):
                if data.status == 'started':
                    self.server_command_queue.put(data)

    def check_for_new_scores(self):
        if self.score_trigger_queue.empty():
            surf_data = np.array(pygame.surfarray.pixels3d(self.canvas)).reshape(-1, 3)
            self.shared_canvas_as_np[:] = surf_data[:]
            del surf_data
            self.score_trigger_queue.put(CalculateScoreMsg())

        while not self.new_score_queue.empty():
            self.scoreboard = self.new_score_queue.get().scores

    def cleanup(self):
        pygame.quit()

        self.server_command_queue.put(QuitMsg())
        self.score_trigger_queue.put(QuitMsg())

        for c in self.clients.values():
            c.command_queue.put(QuitMsg())

        print("Waiting for server to shutdown...")
        self.server_proc.join()

        print("Wait for clients to shutdown...")
        for c in self.clients.values():
            c.process.join()

        self.score_proc.join()
        self.shared_canvas_data.unlink()

    def draw_scoreboard(self, ):
        total_pixels = self.canvas_rect.width * self.canvas_rect.height

        score_rect = pygame.Rect(0, 0, self.tag_size, self.screen_height)

        y = self.tag_size * 1.1
        for color, score in self.scoreboard.items():
            if color not in ClientMeta.colors:
                continue

            percentage = 100 * score / total_pixels
            text = self.font.render(f"  {percentage:.2f}%", True, color)
            self.screen.blit(text, (score_rect.width - text.get_size()[0] - 5, y))
            bar_rect = pygame.Rect(10, y + 30, (score_rect.width - 20) * percentage / 100, 20)
            self.screen.fill(color, bar_rect)
            y += 80
