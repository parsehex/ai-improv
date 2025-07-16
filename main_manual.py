import json
import os
import time
import threading
import queue
import shutil
from typing import Dict, Any

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
import lib.tts as tts

# --- Configuration ---
# File paths for Vuo to read from
LLM_INPUT_FILE = "./data/llm_input.txt"
LLM_OUTPUT_FILE = "./data/llm_output.txt"
APP_STATE_FILE = "./data/app_state.txt"
RECORDED_AUDIO_FILE = "./data/audio.wav"
CURRENT_IMAGE_PATH = "./data/current_character_image.png"
CHARACTERS_DIR = "./data/characters"

# Hotkey for push-to-talk
PUSH_TO_TALK_KEY = keyboard.Key.alt_r

# Audio recording settings
SAMPLE_RATE = 16000  # Whisper models are trained on 16kHz audio
CHANNELS = 1


# --- State Management ---
# Using a class to hold state is cleaner than globals
class AppState:

	def __init__(self):
		self.lock = threading.Lock()
		self.current_state = "Idle"  # Idle, Listening, Processing, etc.
		self.is_recording = False
		self.audio_frames = []
		# A queue to process interactions sequentially
		self.processing_queue = queue.Queue()
		# Character-related state
		self.available_characters: Dict[str, Dict[str, Any]] = {}
		self.current_character_name: str | None = None


state = AppState()


# --- Character Management ---
def load_characters():
	"""Scans the characters directory and loads their configs."""
	print("Loading characters...")
	if not os.path.isdir(CHARACTERS_DIR):
		print(f"Warning: Characters directory not found at {CHARACTERS_DIR}")
		return

	for char_name in os.listdir(CHARACTERS_DIR):
		char_dir = os.path.join(CHARACTERS_DIR, char_name)
		config_path = os.path.join(char_dir, "config.json")
		if os.path.isdir(char_dir) and os.path.isfile(config_path):
			try:
				with open(config_path, 'r') as f:
					config_data = json.load(f)
					# Add a runtime state for the character's current emotion
					config_data['emotion'] = 'neutral'
					state.available_characters[char_name] = config_data
					print(f"  - Loaded character: {config_data['name']}")
			except Exception as e:
				print(f"Error loading character '{char_name}': {e}")

	if state.available_characters:
		# Set the first character found as the default
		state.current_character_name = sorted(state.available_characters.keys())[0]
		print(
		    f"Default character set to: {state.available_characters[state.current_character_name]['name']}"
		)
	else:
		print("No characters found. The application may not function correctly.")


def get_current_character() -> Dict[str, Any] | None:
	"""Safely gets the config dictionary for the current character."""
	if not state.current_character_name:
		return None
	return state.available_characters.get(state.current_character_name)


def get_system_prompt() -> str:
	"""Generates the system prompt for the current character."""
	character = get_current_character()
	if not character:
		return "You are a helpful AI."  # Fallback

	char_name = character.get('name', 'AI')
	# Dynamically get valid emotions from the character's image map
	valid_emotions = [
	    e for e in character.get('images', {}).keys()
	    if e not in ['talking', 'listening', 'thinking']
	]

	return (
	    f"You are a helpful, expressive AI character named {char_name}. "
	    f"Respond in JSON object format with keys: 'text' (spoken output), and optional 'emotion'. "
	    f"Valid emotions are: {valid_emotions}.\n"
	    "Example response:\n"
	    '{"text": "Hello! How can I help you today?", "emotion": "happy"}')


# --- File I/O & State Updates ---
def write_file(filepath, content):
	"""Safely write content to a file, overwriting it."""
	try:
		os.makedirs(os.path.dirname(filepath), exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			f.write(content)
	except Exception as e:
		print(f"Error writing to file {filepath}: {e}")


def update_image_for_state(state_override=None):
	"""Updates character image based on app state or emotion."""
	character = get_current_character()
	if not character:
		return

	image_map = character.get('images', {})
	current_emotion = character.get('emotion', 'neutral')
	image_key = state_override if state_override else current_emotion
	image_path = image_map.get(image_key)

	if image_path and os.path.exists(image_path):
		shutil.copy(image_path, CURRENT_IMAGE_PATH)
		print(f"Updated image to: {image_key}")
	else:
		# Render text as a fallback image
		print(f"Rendering fallback text for state: {image_key}")
		write_file(CURRENT_IMAGE_PATH, image_key.upper())


def update_character_state(new_state: str):
	with state.lock:
		state.current_state = new_state

	print(f"[State Change] => {new_state}")
	write_file(APP_STATE_FILE, new_state)

	# Update the displayed image based on the state
	if new_state in ["Listening", "Thinking", "Talking"]:
		update_image_for_state(new_state.lower())
	elif new_state == "Idle":
		update_image_for_state()  # This will show the character's current emotion


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
    The full pipeline: Transcribe -> LLM -> TTS.
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
	character = get_current_character()
	if not character:
		print("Error: No character loaded.")
		update_character_state("Idle")
		return

	try:
		raw_response = llm.generate(user_text,
		                            sys_input=get_system_prompt(),
		                            json=True)
		parsed = json.loads(raw_response)
		ai_text = parsed.get('text', '')
		emotion = parsed.get('emotion', None)
	except Exception as e:
		print(f"Error parsing LLM response: {e}")
		ai_text = "I'm sorry, something went wrong."
		emotion = None

	write_file(LLM_OUTPUT_FILE, ai_text)

	# Update character's internal emotion state if a valid one was returned
	if emotion and emotion in character.get('images', {}):
		character['emotion'] = emotion

	# 3. TTS Generation and Playback
	update_character_state("Talking")
	tts_audio_path = "./data/output.wav"

	try:
		tts.generate(ai_text,
		             output_path=tts_audio_path,
		             voice=character.get('voice', 'af_heart'))
		print(f"TTS audio saved to {tts_audio_path}")
	except Exception as e:
		print(f"Error generating TTS: {e}")
		update_character_state("Idle")
		return

	# Playback
	try:
		import soundfile as sf
		data, samplerate = sf.read(tts_audio_path, dtype='float32')
		sd.play(data, samplerate)
		sd.wait()  # Wait until playback is done
		print("Playback complete.")
	except Exception as e:
		print(f"Error playing audio: {e}")

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
		start_recording()


def on_release(key):
	with state.lock:
		is_recording_state = state.current_state == "Listening"

	if key == PUSH_TO_TALK_KEY and is_recording_state:
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
	load_characters()
	llm.init()
	stt.init()
	tts.init()
	print("LLM, STT, and TTS models initialized.")

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
		tts.unload()
		write_file(LLM_INPUT_FILE, "")
		write_file(LLM_OUTPUT_FILE, "")
		update_character_state("Offline")
		print("Application stopped.")


if __name__ == "__main__":
	main()
