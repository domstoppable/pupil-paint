import time
from multiprocessing import shared_memory
from uuid import uuid4

import numpy as np

from .messages import CalculateScoreMsg, UpdatedScoresMsg, QuitMsg


SHARE_NAME = f'pupil-paint-{uuid4()}'


def keep_score(width, height, command_queue, data_queue):
    shm = shared_memory.SharedMemory(name=SHARE_NAME, create=False)
    canvas = np.ndarray((width, height, 3), dtype=np.uint8, buffer=shm.buf).reshape(-1, 3)

    while True:
        if not command_queue.empty():
            command = command_queue.get()
            if isinstance(command, QuitMsg):
                break

            elif isinstance(command, CalculateScoreMsg):
                colors, color_counts = np.unique(canvas, axis=0, return_counts=True)
                colors = [tuple(color) for color in colors]
                data_queue.put(UpdatedScoresMsg(dict(zip(colors, color_counts))))

            else:
                print(f"Unknown command: {command}")

        else:
            time.sleep(0.1)
