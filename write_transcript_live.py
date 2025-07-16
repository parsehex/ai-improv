from whisper_live.client import TranscriptionClient
import threading
import time
import config as cfg


# Default callback for standalone execution
def _default_render_callback(text: str, segments: list):
	output_file = "./data/live_transcript_output.txt"
	lock = threading.Lock()

	# Simple logic to display last 5 completed lines
	completed_segments = [
	    s['text'].strip() for s in segments if s.get('completed')
	]
	last_n_segments = completed_segments[-5:]
	file_content = '\n'.join(last_n_segments)

	with lock:
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write(file_content)


def start_transcription(callback=_default_render_callback):
	"""
    Initializes and starts the TranscriptionClient in a background thread.

    Args:
        callback: A function that handles the transcription output.
                  It receives `text` (str) and `segments` (list).
    """
	client = TranscriptionClient(
	    cfg.WHISPER_SERVER_IP,
	    cfg.WHISPER_SERVER_PORT,
	    translate=False,
	    model=cfg.WHISPER_MODEL,
	    use_vad=True,
	    max_clients=4,
	    clip_audio=True,
	    max_connection_time=9999,
	    transcription_callback=callback,
	    mute_audio_playback=False,
	)

	# The client's __call__ method is blocking, so run it in a thread
	client_thread = threading.Thread(target=client, daemon=True)
	client_thread.start()
	print("Transcription client started in the background.")


if __name__ == "__main__":
	print("Running live transcript writer in standalone mode.")
	print(f"Writing rolling transcript to ./data/live_transcript_output.txt")
	start_transcription()

	# Keep the main thread alive to let the background thread run
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		print("\nStopping.")
