import json
import os
import time
import threading
import queue
import shutil
import asyncio
from typing import List, Dict, Any

# --- Web Server Imports ---
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

# --- Dependencies for manual recording ---
from pynput import keyboard
import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np

# --- Project Imports ---
import lib.llm as llm
import lib.stt as stt
import lib.tts as tts

# --- Configuration ---
LLM_INPUT_FILE = "./data/llm_input.txt"
LLM_OUTPUT_FILE = "./data/llm_output.txt"
APP_STATE_FILE = "./data/app_state.txt"
RECORDED_AUDIO_FILE = "./data/audio.wav"
CURRENT_IMAGE_PATH = "./data/current_character_image.png"
CHARACTERS_DIR = "./data/characters"
PUSH_TO_TALK_KEY = keyboard.Key.alt_r
SAMPLE_RATE = 16000
CHANNELS = 1


# --- WebSocket Connection Manager ---
class ConnectionManager:

	def __init__(self):
		self.active_connections: List[WebSocket] = []

	async def connect(self, websocket: WebSocket):
		await websocket.accept()
		self.active_connections.append(websocket)

	def disconnect(self, websocket: WebSocket):
		self.active_connections.remove(websocket)

	async def broadcast(self, message: dict):
		for connection in self.active_connections:
			await connection.send_json(message)


manager = ConnectionManager()


# --- State Management ---
class AppState:

	def __init__(self):
		self.lock = threading.Lock()
		self.current_state = "Idle"
		self.is_recording = False
		self.audio_frames = []
		self.processing_queue = queue.Queue()
		self.state_update_queue = asyncio.Queue()

		self.available_characters: Dict[str, Dict[str, Any]] = {}
		self.current_character_name: str | None = None


state = AppState()
app = FastAPI()


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
		state.current_character_name = sorted(state.available_characters.keys())[0]
		print(f"Default character set to: {state.current_character_name}")
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
	# Dynamically get valid emotions, excluding non-emotional states
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


async def switch_character(char_name: str):
	"""Switches the active character and notifies clients."""
	should_update = False
	with state.lock:
		# The lock is only held for this small, critical section
		if char_name in state.available_characters and char_name != state.current_character_name:
			print(f"Switching character to: {char_name}")
			prev_char_config = get_current_character()
			assert prev_char_config is not None
			prev_emotion = prev_char_config.get('emotion', 'neutral')
			state.current_character_name = char_name
			char_config = get_current_character()
			assert char_config is not None
			char_config['emotion'] = prev_emotion
			should_update = True
		else:
			print(
			    f"Could not switch to character '{char_name}'. Not found or already active."
			)

	# If a change was made, perform all side-effects outside the lock
	if should_update:
		# This call is now safe, as the lock is released.
		update_character_state("Idle")

		# The broadcast is also safely outside the lock.
		await manager.broadcast({
		    "type": "character_update",
		    "character": get_public_character_data()
		})


# --- File I/O & State Updates ---
def write_file(filepath, content):
	try:
		os.makedirs(os.path.dirname(filepath), exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			f.write(content)
	except Exception as e:
		print(f"Error writing to file {filepath}: {e}")


def update_image_for_state(state_override=None):
	character = get_current_character()
	if not character: return

	image_map = character.get('images', {})
	current_emotion = character.get('emotion', 'neutral')
	image_key = state_override if state_override else current_emotion
	image_path = image_map.get(image_key)

	if image_path and os.path.exists(image_path):
		shutil.copy(image_path, CURRENT_IMAGE_PATH)
	else:
		print(f"No image found for state: {image_key} at path: {image_path}")


def update_character_state(new_state: str):
	with state.lock:
		state.current_state = new_state
	print(f"[State Change] => {new_state}")
	write_file(APP_STATE_FILE, new_state)
	state.state_update_queue.put_nowait(new_state)

	if new_state in ["Listening", "Thinking", "Talking"]:
		update_image_for_state(new_state.lower())
	elif new_state == "Idle":
		update_image_for_state()


# --- Audio Recording ---
stream = None


def start_recording():
	global stream
	with state.lock:
		if state.is_recording or state.current_state != "Idle": return
		state.is_recording = True
		state.audio_frames = []
	update_character_state("Listening")

	def audio_callback(indata, frames, time, status):
		if status: print(f"Audio stream status: {status}")
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
		if not state.is_recording: return
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
		state.audio_frames = []
	write(RECORDED_AUDIO_FILE, SAMPLE_RATE, audio_data)
	state.processing_queue.put(RECORDED_AUDIO_FILE)


# --- Core Logic ---
def process_interaction(audio_path: str):
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
	if emotion and emotion in character.get('images', {}):
		character['emotion'] = emotion

	update_character_state("Talking")
	tts_audio_path = "./data/output.wav"
	try:
		tts.generate(ai_text,
		             output_path=tts_audio_path,
		             voice=character.get('voice', 'af_heart'))
	except Exception as e:
		print(f"Error generating TTS: {e}")
		update_character_state("Idle")
		return

	try:
		import soundfile as sf
		data, samplerate = sf.read(tts_audio_path, dtype='float32')
		sd.play(data, samplerate)
		sd.wait()
	except Exception as e:
		print(f"Error playing audio: {e}")

	update_character_state("Idle")
	print("\nReady for next interaction.")


def processing_worker():
	while True:
		audio_path = state.processing_queue.get()
		if audio_path is None: break
		process_interaction(audio_path)
		state.processing_queue.task_done()


# --- Hotkey Handling ---
def on_press(key):
	if key == PUSH_TO_TALK_KEY: start_recording()


def on_release(key):
	if key == PUSH_TO_TALK_KEY: stop_recording()


# --- Web Server Endpoints ---
def get_public_character_data():
	"""Returns a dictionary of public-facing character data."""
	all_chars = {}
	for char_key, char_data in state.available_characters.items():
		all_chars[char_key] = {
		    "name": char_data.get("name"),
		    "voice": char_data.get("voice")
		}
	return {"available": all_chars, "current": state.current_character_name}


@app.get("/api/characters", response_class=JSONResponse)
async def get_characters():
	return get_public_character_data()


@app.get("/", response_class=HTMLResponse)
async def get_remote_control():
	with open("remote_control/templates/index.html") as f:
		return HTMLResponse(content=f.read(), status_code=200)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
	await manager.connect(websocket)
	await websocket.send_json({
	    "type": "state_update",
	    "state": state.current_state
	})
	await websocket.send_json({
	    "type": "character_update",
	    "character": get_public_character_data()
	})
	try:
		while True:
			data = await websocket.receive_json()
			action = data.get("action")
			if action == "start_recording":
				start_recording()
			elif action == "stop_recording":
				stop_recording()
			elif action == "switch_character":
				char_name = data.get("character")
				if char_name:
					await switch_character(char_name)
	except WebSocketDisconnect:
		manager.disconnect(websocket)
		print("Client disconnected")


# --- Main Application ---
async def state_updater():
	"""Task to broadcast state changes from the queue to all clients."""
	while True:
		new_state = await state.state_update_queue.get()
		await manager.broadcast({"type": "state_update", "state": new_state})
		state.state_update_queue.task_done()


@app.on_event("startup")
def startup_event():
	print("Starting AI Improv (Web Remote Mode)...")
	load_characters()
	print(f"Hold the '{PUSH_TO_TALK_KEY}' key to record your voice.")
	print("Or open http://127.0.0.1:8000 in your browser.")

	llm.init()
	stt.init()
	tts.init()
	print("LLM, STT, and TTS models initialized.")

	write_file(LLM_INPUT_FILE, "")
	write_file(LLM_OUTPUT_FILE, "")
	update_character_state("Idle")

	threading.Thread(target=processing_worker, daemon=True).start()
	keyboard.Listener(on_press=on_press, on_release=on_release).start()
	asyncio.create_task(state_updater())
	print("\nReady for interaction.")


@app.on_event("shutdown")
def shutdown_event():
	print("\nShutting down.")
	state.processing_queue.put(None)
	llm.unload()
	stt.unload()
	tts.unload()
	write_file(APP_STATE_FILE, "Offline")
	print("Application stopped.")


if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
