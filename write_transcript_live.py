from whisper_live.client import TranscriptionClient
from collections import deque
import threading
import time

lock = threading.Lock()

output_file = "./data/live_transcript_output.txt"
start_time = time.time()


def render_transcript_snippet(text: str,
                              segments: list,
                              last_type='sec',
                              last_n=30,
                              completed_only=True):
	# last_type:
	# 	'line': show last N lines/segments in file
	# 	'sec': show segments from last N seconds
	file_content = ''

	subset = segments
	if last_type == 'line':  # pick last N segments
		subset = segments[-last_n:]

	now = time.time()
	cur_runtime = now - start_time
	for segment in subset:
		text = segment.get('text', '').strip()
		if not text:
			continue

		is_complete = segment.get('completed')
		if completed_only and not is_complete:  # skip if incomplete
			continue

		if last_type == 'sec':  # pick last N seconds
			end = float(segment.get('end', '').strip())
			since_end = cur_runtime - end
			if since_end > last_n:
				continue

		file_content += text + '\n'

	with lock:
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write(file_content)


client = TranscriptionClient(
    "192.168.0.217",
    9090,
    translate=False,
    model="medium.en",
    use_vad=True,
    # save_output_recording=True,
    # output_recording_filename="./output_recording.wav",
    max_clients=4,
    clip_audio=True,
    max_connection_time=9999,  # Can't set to infinity or similar
    transcription_callback=render_transcript_snippet,
    # log_transcription=False, # callback isn't called when False
    mute_audio_playback=False,
)
client()
