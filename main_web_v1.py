import json
import os
import time
import threading
import queue
import shutil
import asyncio
from typing import List

# --- Web Server Imports ---
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

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
PUSH_TO_TALK_KEY = keyboard.Key.alt_r
SAMPLE_RATE = 16000
CHANNELS = 1

with open('./data/character_images/available_images.json') as f:
	image_map = json.load(f)

sys_prompt = (
    "You are a helpful, expressive AI character named Luna. "
    "Respond in JSON object format with keys: 'text' (spoken output), and optional 'emotion'. "
    "Valid emotions are: ['neutral', 'happy', 'surprised'].\n"
    "Example response:\n"
    '{"text": "Hello! How can I help you today?", "emotion": "happy"}')


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
		self.current_emotion = "neutral"
		self.is_recording = False
		self.audio_frames = []
		self.processing_queue = queue.Queue()
		# Queue for thread-safe state updates to be broadcast over WebSocket
		self.state_update_queue = asyncio.Queue()


state = AppState()
app = FastAPI()


# --- File I/O & State Updates ---
def write_file(filepath, content):
	try:
		os.makedirs(os.path.dirname(filepath), exist_ok=True)
		with open(filepath, 'w', encoding='utf-8') as f:
			f.write(content)
	except Exception as e:
		print(f"Error writing to file {filepath}: {e}")


def update_image_for_state(state_override=None):
	image_key = state_override if state_override else state.current_emotion
	image_path = image_map.get(image_key)
	if image_path:
		shutil.copy(image_path, CURRENT_IMAGE_PATH)
	else:
		print(f"No image found for state: {image_key}")


def update_character_state(new_state: str):
	with state.lock:
		state.current_state = new_state
	print(f"[State Change] => {new_state}")
	write_file(APP_STATE_FILE, new_state)

	# Put the state update on the asyncio queue to be broadcast by the main thread
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
		if state.is_recording or state.current_state != "Idle":
			return
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
	try:
		raw_response = llm.generate(user_text, sys_input=sys_prompt, json=True)
		parsed = json.loads(raw_response)
		ai_text = parsed.get('text', '')
		emotion = parsed.get('emotion', None)
	except Exception as e:
		print(f"Error parsing LLM response: {e}")
		ai_text = "I'm sorry, something went wrong."
		emotion = None

	write_file(LLM_OUTPUT_FILE, ai_text)
	if emotion and emotion in image_map: state.current_emotion = emotion

	update_character_state("Talking")
	tts_audio_path = "./data/output.wav"
	try:
		tts.generate(ai_text, output_path=tts_audio_path)
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
@app.get("/", response_class=HTMLResponse)
async def get_remote_control():
	# Load the HTML file from a 'remote_control/templates' directory
	with open("remote_control/templates/index.html") as f:
		return HTMLResponse(content=f.read(), status_code=200)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
	await manager.connect(websocket)
	# Send current state on connect
	await websocket.send_json({
	    "type": "state_update",
	    "state": state.current_state
	})
	try:
		while True:
			data = await websocket.receive_json()
			action = data.get("action")
			if action == "start_recording":
				start_recording()
			elif action == "stop_recording":
				stop_recording()
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
	print(f"Hold the '{PUSH_TO_TALK_KEY}' key to record your voice.")
	print("Or open http://127.0.0.1:8000 in your browser.")

	# Initialize models
	llm.init()
	stt.init()
	tts.init()
	print("LLM, STT, and TTS models initialized.")

	# Clear/initialize Vuo files
	write_file(LLM_INPUT_FILE, "")
	write_file(LLM_OUTPUT_FILE, "")
	update_character_state("Idle")

	# Start background threads
	threading.Thread(target=processing_worker, daemon=True).start()
	keyboard.Listener(on_press=on_press, on_release=on_release).start()

	# Start the async task for broadcasting state updates
	asyncio.create_task(state_updater())
	print("\nReady for interaction.")


@app.on_event("shutdown")
def shutdown_event():
	print("\nShutting down.")
	state.processing_queue.put(None)  # Signal worker to exit
	llm.unload()
	stt.unload()
	tts.unload()
	write_file(APP_STATE_FILE, "Offline")
	print("Application stopped.")


if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)
