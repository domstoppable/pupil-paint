import pygame
import io
import qrcode

import numpy as np
import cv2

from pupil_labs.real_time_screen_gaze import marker_generator


def cv_to_surf(data):
    fixed_axes = data.swapaxes(0, 1)
    return pygame.surfarray.make_surface(fixed_axes)


def make_marker(marker_id, tag_size):
    marker_pixels = marker_generator.generate_marker(marker_id=marker_id, flip_x=True, flip_y=True)
    marker_pixels = np.pad(marker_pixels, 1, constant_values=255)
    marker_pixels = cv2.cvtColor(marker_pixels, cv2.COLOR_GRAY2RGB)
    surf = cv_to_surf(marker_pixels)

    return pygame.transform.scale(surf, (tag_size, tag_size))


def make_qr(data, size):
    qr_image = qrcode.make(data)
    image_buffer = io.BytesIO()
    qr_image.save(image_buffer)
    image_buffer.seek(0)
    surf = pygame.image.load(image_buffer, 'PNG')

    return pygame.transform.scale(surf, (size, size))
