import multiprocessing as mp
import random
from pathlib import Path

import pygame

from .server import run_server
from .client import get_surface_gazes
from .local_ip import get_local_ip
from .messages import QuitMsg, ClientStatusMsg, GazePointMsg, SwatchesMsg, SwatchSelectionMsg
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
        if color is None:
            color = ClientMeta.colors[0]

        self.host = host
        self.color = tuple(color)
        self.command_queue = mp.Queue()
        self.data_queue = data_queue

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
        self.server_proc = mp.Process(target=run_server, args=(self.server_command_queue, self.client_info_queue))

        self.tag_size = 200
        self.scoreboard = {}

    def run(self):
        pygame.init()
        self.server_proc.start()

        #self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.screen = pygame.display.set_mode((1920, 1080))
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
        self.canvas = pygame.Surface((self.canvas_rect.width, self.canvas_rect.height))
        self.canvas.fill((0, 0, 0))

        # Clock to control frame rate
        clock = pygame.time.Clock()

        self.clients = {}

        self.server_command_queue.put(SwatchesMsg(ClientMeta.colors))

        self.running = True
        while self.running:
            self.check_for_events()
            if not self.running:
                break

            self.check_for_new_clients()
            self.check_for_new_gazes()

            # paint the updated canvas to the screen
            self.screen.fill((128, 128, 128), self.canvas_rect.inflate(10, 10))
            self.screen.blit(self.canvas, (self.canvas_rect.x, self.canvas_rect.y))

            # paint the scoreboard
            self.draw_scoreboard()

            # paint the markers
            self.screen.blit(markers[0], (0, 0))
            self.screen.blit(markers[1], ((self.screen_width - self.tag_size) / 2, 0))
            self.screen.blit(markers[2], (self.screen_width - self.tag_size, 0))
            self.screen.blit(markers[3], (self.screen_width - self.tag_size, self.screen_height - self.tag_size))
            self.screen.blit(markers[4], (0, self.screen_height - self.tag_size))
            self.screen.blit(qr_image, ((self.screen_width - qr_image.get_size()[0]) / 2, self.screen_height - qr_image.get_size()[1]))

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
                    if client.color not in self.scoreboard:
                        self.scoreboard[client.color] = 0

                    self.clients[client_ip] = client
                    print("Starting client", client_ip)

            elif isinstance(message, SwatchSelectionMsg):
                client = self.clients[message.host]

                client.color = message.color
                if client.color not in self.scoreboard:
                    self.scoreboard[client.color] = 0

    def check_for_new_gazes(self):
        while not self.gaze_data_queue.empty():
            data = self.gaze_data_queue.get()
            if isinstance(data, GazePointMsg):
                gaze_pos = data.x, data.y
                client_info = self.clients[data.host]

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

                    # Update color count for the painted area
                    for x in range(brush_rect.left, brush_rect.right):
                        for y in range(brush_rect.top, brush_rect.bottom):
                            if 0 <= x < self.canvas_rect.width and 0 <= y < self.canvas_rect.height:
                                old_color = target_area.get_at((x - brush_rect.left, y - brush_rect.top))
                                old_color = (old_color.r, old_color.g, old_color.b)
                                if old_color in self.scoreboard:
                                    self.scoreboard[old_color] -= 1

                                new_color = self.canvas.get_at((x, y))
                                new_color = (new_color.r, new_color.g, new_color.b)
                                if new_color in self.scoreboard:
                                    self.scoreboard[new_color] += 1
                                elif new_color in ClientMeta.colors:
                                    self.scoreboard[new_color] = 1

            elif isinstance(data, ClientStatusMsg):
                if data.status == 'started':
                    self.server_command_queue.put(data)

    def cleanup(self):
        pygame.quit()

        self.server_command_queue.put(QuitMsg())

        for c in self.clients.values():
            c.command_queue.put(QuitMsg())

        print("Waiting for server to shutdown...")
        self.server_proc.join()

        print("Wait for clients to shutdown...")
        for c in self.clients.values():
            c.process.join()

    def draw_scoreboard(self, ):
        total_pixels = self.canvas_rect.width * self.canvas_rect.height

        score_rect = pygame.Rect(0, 0, self.tag_size, self.screen_height)
        self.screen.fill((0, 0, 0), score_rect)

        y = self.tag_size * 1.1
        for color, score in self.scoreboard.items():
            percentage = 100 * score / total_pixels
            text = self.font.render(f"  {percentage:.2f}%", True, color)
            self.screen.blit(text, (score_rect.width - text.get_size()[0] - 5, y))
            bar_rect = pygame.Rect(10, y + 30, (score_rect.width - 20) * percentage / 100, 20)
            self.screen.fill(color, bar_rect)
            y += 80

