import socket


def get_local_ip():
	"""Tries to determine the local IP address of the machine."""
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		# Doesn't even have to be reachable
		s.connect(('10.255.255.255', 1))
		IP = s.getsockname()[0]
	except Exception:
		IP = '127.0.0.1'  # Fallback
	finally:
		s.close()
	return IP
