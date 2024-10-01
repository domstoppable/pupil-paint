from pathlib import Path
import json

from pupil_labs.realtime_api.simple import Device
from pupil_labs.real_time_screen_gaze.gaze_mapper import GazeMapper

from .messages import ClientStatusMsg, GazePointMsg, QuitMsg


def get_surface_gazes(host, marker_verts, surf_size, command_queue, data_queue):
    device = Device(host, 8080)

    if device.module_serial is None:
        if device.serial_number_glasses is not None:
            json_path = Path(__file__).parent / 'pi-intrinsics.json'
            with json_path.open('rt') as json_file:
                json_data = json.load(json_file)
                calibration = {
                    'scene_camera_matrix': json_data['camera_matrix'],
                    'scene_distortion_coefficients': json_data['dist_coefs'],
                }
    else:
        calibration = device.get_calibration()

    gaze_mapper = GazeMapper(calibration)
    screen_surface = gaze_mapper.add_surface(marker_verts, surf_size)

    # receive one frame to initiate the stream
    device.receive_matched_scene_video_frame_and_gaze()
    data_queue.put(ClientStatusMsg(host, 'started'))

    keep_running = True
    while keep_running:
        while not command_queue.empty():
            command = command_queue.get()
            if isinstance(command, QuitMsg):
                keep_running = False
            else:
                print(f"Unknown command: {command}")

        if not keep_running:
            break

        data = device.receive_matched_scene_video_frame_and_gaze(1 / 60)
        if data is None:
            continue

        result = gaze_mapper.process_frame(*data)
        for surface_gaze in result.mapped_gaze[screen_surface.uid]:
            data_queue.put(GazePointMsg(
                host,
                surface_gaze.x * surf_size[0],
                (1 - surface_gaze.y) * surf_size[1]
            ))

    device.close()
