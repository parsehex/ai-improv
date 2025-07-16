# This whole thing works _okay_, but not great. I'm thinking that manually recording / stopping would be better.

import time
import threading

# Project imports
from write_transcript_live import start_transcription
import lib.llm as llm
# import lib.tts as tts # For later

# --- Configuration ---
# File paths for Vuo to read from
LLM_INPUT_FILE = "./data/llm_input.txt"
LLM_OUTPUT_FILE = "./data/llm_output.txt"
LIVE_TRANSCRIPT_FILE = "./data/live_transcript_output.txt"
CHARACTER_STATE_FILE = "./data/app_state.txt"

# Conversation logic settings
PAUSE_THRESHOLD_S = 2.0  # Seconds of silence to trigger LLM response
ROLLING_TRANSCRIPT_LINES = 5  # Number of lines to show in the live transcript


# --- State Management ---
# A class to hold state, which is cleaner than using globals
class AppState:

	def __init__(self):
		self.lock = threading.Lock()
		self.full_transcript_segments = []
		self.last_speech_time = time.time()
		self.is_character_speaking = False
		# Tracks how many transcript segments we've already sent to the LLM
		self.processed_segment_count = 0


state = AppState()


# --- File I/O ---
def write_file(filepath, content):
	"""Safely write content to a file, overwriting it."""
	try:
		with open(filepath, 'w', encoding='utf-8') as f:
			f.write(content)
	except Exception as e:
		print(f"Error writing to file {filepath}: {e}")


# --- Core Logic ---


def handle_llm_interaction():
	"""
    Processes the user's latest speech, gets an LLM response, and updates Vuo files.
    This function is called from the main loop when a pause is detected.
    """
	with state.lock:
		# Get only the new segments since the last turn
		new_segments = state.full_transcript_segments[state.
		                                              processed_segment_count:]
		turn_segments = [s for s in new_segments if s['text'].strip()]

		if not turn_segments:
			return

		# Mark these segments as processed *before* the LLM call
		state.processed_segment_count = len(state.full_transcript_segments)
		llm_input_text = " ".join([s['text'].strip() for s in turn_segments])

	# --- The rest of the logic can be outside the lock to not block the transcriber ---
	print(f"\n[USER] {llm_input_text}")
	write_file(LLM_INPUT_FILE, llm_input_text)
	write_file(CHARACTER_STATE_FILE, "Thinking...")

	try:
		llm_response = llm.generate(llm_input_text)
	except Exception as e:
		print(f"Error generating LLM response: {e}")
		llm_response = "I'm sorry, I had a problem thinking of a response."

	print(f"[AI] {llm_response}")
	write_file(LLM_OUTPUT_FILE, llm_response)

	# --- TTS and State Change ---
	state.is_character_speaking = True
	write_file(CHARACTER_STATE_FILE, "Talking")
	print("(TTS playback would happen here)")
	# TODO: Replace this sleep with your actual TTS playback function.
	# The `is_character_speaking` flag will prevent the app from transcribing its own speech.
	time.sleep(3)  # Placeholder for TTS playback duration
	state.is_character_speaking = False

	write_file(CHARACTER_STATE_FILE, "Listening")
	# Clear the user input file now that the turn is over
	write_file(LLM_INPUT_FILE, "")


def transcription_callback(text: str, segments: list):
	"""
    This function is called by the live transcriber on each update.
    It updates the shared state with the latest transcript data.
    """
	with state.lock:
		# If character is speaking, ignore transcription to prevent feedback loops.
		# We also reset the processed segment count to ignore anything the user
		# might have said while the character was talking.
		if state.is_character_speaking:
			state.processed_segment_count = len(segments)
			return

		state.last_speech_time = time.time()
		state.full_transcript_segments = segments

		# Update the live transcript file for Vuo with a rolling window of text
		rolling_transcript_segments = segments[-ROLLING_TRANSCRIPT_LINES:]
		rolling_transcript = "\n".join(
		    [s['text'].strip() for s in rolling_transcript_segments])
		write_file(LIVE_TRANSCRIPT_FILE, rolling_transcript)


def main():
	"""Main application entry point."""
	print("Starting AI Improv application...")

	# Initialize components
	llm.init()
	print("LLM initialized.")

	# Clear/initialize Vuo files on startup
	write_file(LLM_INPUT_FILE, "")
	write_file(LLM_OUTPUT_FILE, "")
	write_file(LIVE_TRANSCRIPT_FILE, "")
	write_file(CHARACTER_STATE_FILE, "Listening")

	# Start transcription in the background with our custom callback
	start_transcription(callback=transcription_callback)

	print(f"Application is running. Speak into the microphone.")
	print(f"Will respond after {PAUSE_THRESHOLD_S}s of silence.")

	try:
		# The main loop polls for a pause in speech to trigger the chat logic.
		while True:
			with state.lock:
				is_paused = (time.time() - state.last_speech_time) > PAUSE_THRESHOLD_S
				has_new_speech = len(
				    state.full_transcript_segments) > state.processed_segment_count

			if is_paused and has_new_speech:
				handle_llm_interaction()
				# Reset the pause timer to prevent immediate re-triggering
				with state.lock:
					state.last_speech_time = time.time()

			time.sleep(0.1)

	except KeyboardInterrupt:
		print("\nShutting down.")
	finally:
		# Cleanup Vuo files on exit
		write_file(LIVE_TRANSCRIPT_FILE, "")
		write_file(CHARACTER_STATE_FILE, "Offline")


if __name__ == "__main__":
	main()
