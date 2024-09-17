import socket


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('123.123.123.123', 123))
            return s.getsockname()[0]
    except Exception as e:
        print(f"Error determining IP: {e}")
