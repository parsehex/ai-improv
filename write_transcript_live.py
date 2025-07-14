from whisper_live.client import TranscriptionClient
from collections import deque
import threading
import time

lock = threading.Lock()

completed_segments = deque(maxlen=4)
incomplete_segment = None

# Output file path
output_file = "./data/live_transcript_output.txt"

start_time = time.time()


def render_transcript_snippet(text: str,
                              segments: list,
                              last_type='sec',
                              last_n=30):
	# simply write the last N segments of transcript to the file, including incomplete
	# TODO maybe write incomplete line to separate file, display differently
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

		if last_type == 'sec':  # pick last N seconds
			end = float(segment.get('end', '').strip())
			since_end = cur_runtime - end
			if since_end > last_n:
				continue

		file_content += text + '\n'

	with lock:
		with open(output_file, 'w', encoding='utf-8') as f:
			f.write(file_content)


def transcription_cb(text, segments):
	global completed_segments, incomplete_segment

	updated = False

	for segment in segments:
		text = segment.get('text', '').strip()
		if not text:
			continue

		if segment.get('completed', False):
			# Only add if it's new (to avoid re-adding the same completed segment)
			if not completed_segments or completed_segments[-1] != text:
				completed_segments.append(text)
				updated = True
			# Clear any previous incomplete since it's now complete
			incomplete_segment = None
		else:
			# Update the current incomplete segment
			incomplete_segment = text
			updated = True

	if updated:
		with lock:
			with open(output_file, 'w', encoding='utf-8') as f:
				for line in completed_segments:
					f.write(line + '\n')
				if incomplete_segment:
					f.write(incomplete_segment + '\n')


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
