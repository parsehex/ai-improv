# main_manual.py

import os
import time
import threading
import queue

# --- Dependencies for manual recording ---
# You'll need to install these:
# pip install pynput sounddevice scipy numpy
# On macOS, you might need to install portaudio first: brew install portaudio
from pynput import keyboard
import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np

# --- Project Imports ---
import lib.llm as llm
import lib.stt as stt
# import lib.tts as tts # For later

# --- Configuration ---
# File paths for Vuo to read from
LLM_INPUT_FILE = "./data/llm_input.txt"
LLM_OUTPUT_FILE = "./data/llm_output.txt"
CHARACTER_STATE_FILE = "./data/character_state.txt"
RECORDED_AUDIO_FILE = "./data/audio.wav"

# Hotkey for push-to-talk
# Using right option/alt key. You can change this.
# See pynput docs for key names: https://pynput.readthedocs.io/en/latest/keyboard.html
PUSH_TO_TALK_KEY = keyboard.Key.cmd_r

# Audio recording settings
SAMPLE_RATE = 16000  # Whisper models are trained on 16kHz audio
CHANNELS = 1


# --- State Management ---
# Using a class to hold state is cleaner than globals
class AppState:

	def __init__(self):
		self.lock = threading.Lock()
		self.current_state = "Idle"  # Idle, Listening, Processing
		self.is_recording = False
		self.audio_frames = []
		# A queue to process interactions sequentially
		self.processing_queue = queue.Queue()


state = AppState()


# --- File I/O ---
def write_file(filepath, content):
	"""Safely write content to a file, overwriting it."""
	try:
		# Ensure directory exists
		os.makedirs(os.path.dirname(filepath), exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			f.write(content)
	except Exception as e:
		print(f"Error writing to file {filepath}: {e}")


def update_character_state(new_state: str):
	"""Updates the state variable and the file for Vuo."""
	with state.lock:
		state.current_state = new_state
	print(f"[State Change] => {new_state}")
	write_file(CHARACTER_STATE_FILE, new_state)


# --- Audio Recording ---
stream = None


def start_recording():
	global stream
	with state.lock:
		if state.is_recording:
			return
		state.is_recording = True
		state.audio_frames = []

	update_character_state("Listening")

	def audio_callback(indata, frames, time, status):
		"""This is called (from a separate thread) for each audio block."""
		if status:
			print(f"Audio stream status: {status}")
		with state.lock:
			if state.is_recording:
				state.audio_frames.append(indata.copy())

	stream = sd.InputStream(samplerate=SAMPLE_RATE,
	                        channels=CHANNELS,
	                        callback=audio_callback,
	                        dtype='float32')
	stream.start()
	print("Recording started...")


def stop_recording():
	global stream
	with state.lock:
		if not state.is_recording:
			return
		state.is_recording = False

	if stream:
		stream.stop()
		stream.close()
		stream = None

	print("Recording stopped.")
	update_character_state("Processing")

	with state.lock:
		if not state.audio_frames:
			print("No audio recorded.")
			update_character_state("Idle")
			return
		audio_data = np.concatenate(state.audio_frames, axis=0)
		state.audio_frames = []  # Clear frames

	write(RECORDED_AUDIO_FILE, SAMPLE_RATE, audio_data)
	print(f"Audio saved to {RECORDED_AUDIO_FILE}")

	# Put the file path on the queue for the processing thread
	state.processing_queue.put(RECORDED_AUDIO_FILE)


# --- Core Logic ---
def process_interaction(audio_path: str):
	"""
    The full pipeline: Transcribe -> LLM -> TTS (placeholder).
    This runs in a separate thread to not block the main app.
    """
	# 1. Transcribe Audio
	update_character_state("Transcribing...")
	try:
		transcription_result = stt.generate(audio_path, verbose=False)
		user_text = transcription_result.text.strip()
		if not user_text:
			print("No speech detected in audio.")
			update_character_state("Idle")
			return
	except Exception as e:
		print(f"Error during transcription: {e}")
		update_character_state("Idle")
		return

	print(f"\n[USER] {user_text}")
	write_file(LLM_INPUT_FILE, user_text)

	# 2. Get LLM Response
	update_character_state("Thinking...")
	try:
		llm_response = llm.generate(user_text)
	except Exception as e:
		print(f"Error generating LLM response: {e}")
		llm_response = "I'm sorry, I had a problem thinking of a response."

	print(f"[AI] {llm_response}")
	write_file(LLM_OUTPUT_FILE, llm_response)

	# 3. TTS Playback (Placeholder)
	update_character_state("Talking")
	print("(TTS playback would happen here)")
	# TODO: Replace this sleep with your actual TTS playback function.
	time.sleep(3)  # Placeholder for TTS playback duration

	# 4. Cleanup and Reset
	update_character_state("Idle")
	print("\nReady for next interaction. Hold Right Alt to speak.")


def processing_worker():
	"""A worker thread that waits for tasks on the queue and processes them."""
	while True:
		audio_path = state.processing_queue.get()
		if audio_path is None:  # A 'None' value signals the thread to exit
			break
		process_interaction(audio_path)
		state.processing_queue.task_done()


# --- Hotkey Handling ---
def on_press(key):
	with state.lock:
		is_idle = state.current_state == "Idle"

	if key == PUSH_TO_TALK_KEY and is_idle:
		print('Press')
		start_recording()


def on_release(key):
	with state.lock:
		is_recording_state = state.current_state == "Listening"

	if key == PUSH_TO_TALK_KEY and is_recording_state:
		print('Release')
		stop_recording()


# --- Main Application ---
def main():
	"""Main application entry point."""
	print("Starting AI Improv (Manual Mode)...")
	print(f"Hold the '{PUSH_TO_TALK_KEY}' key to record your voice.")
	print(
	    "NOTE: On macOS, you may need to grant Accessibility permissions to your terminal/IDE."
	)

	# Initialize components (can take a moment)
	llm.init()
	stt.init()
	print("LLM and STT models initialized.")

	# Clear/initialize Vuo files on startup
	write_file(LLM_INPUT_FILE, "")
	write_file(LLM_OUTPUT_FILE, "")
	update_character_state("Idle")

	# Start the background thread for processing interactions
	processing_thread = threading.Thread(target=processing_worker, daemon=True)
	processing_thread.start()

	# Start listening for hotkeys
	listener = keyboard.Listener(on_press=on_press, on_release=on_release)
	listener.start()
	print("\nHotkey listener started. Ready for interaction.")

	try:
		# The main thread will block here until the listener is stopped.
		listener.join()
	except KeyboardInterrupt:
		print("\nShutting down.")
	finally:
		# Cleanup
		if listener.is_alive():
			listener.stop()

		# Stop the processing thread gracefully
		state.processing_queue.put(None)
		processing_thread.join()

		llm.unload()
		stt.unload()
		update_character_state("Offline")
		print("Application stopped.")


if __name__ == "__main__":
	main()
