import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import soundfile as sf
import numpy as np

# Assuming 'lib' is in the python path.
# If running from the root dir, you might need to add it:
# import sys
# sys.path.append('.')
import lib.llm as llm
import lib.stt as stt
import lib.tts as tts

# --- App & Models ---
app = FastAPI()


@app.on_event("startup")
def startup_event():
	print("Initializing AI models...")
	llm.init()
	stt.init()
	tts.init()
	print("Models initialized.")


@app.on_event("shutdown")
def shutdown_event():
	print("Unloading AI models...")
	llm.unload()
	stt.unload()
	tts.unload()
	print("Models unloaded.")


# --- API Endpoints ---


@app.post("/stt")
async def speech_to_text(audio_file: UploadFile = File(...)):
	"""
    Accepts an audio file and returns the transcribed text.
    """
	try:
		# Save temporary file to be read by the STT library
		temp_audio_path = "data/temp_stt_input.wav"
		with open(temp_audio_path, "wb") as f:
			f.write(await audio_file.read())

		result = stt.generate(temp_audio_path, verbose=False)
		return {"text": result.text.strip()}
	except Exception as e:
		print(f"STT Error: {e}")
		raise HTTPException(status_code=500, detail=str(e))


class LLMRequest(BaseModel):
	prompt: str
	system_prompt: str


@app.post("/llm")
async def language_model_generate(request: LLMRequest):
	"""
    Accepts a user prompt and system prompt, returns the model's response.
    """
	try:
		response = llm.generate(request.prompt,
		                        sys_input=request.system_prompt,
		                        json=True)
		return json.loads(response)
	except Exception as e:
		print(f"LLM Error: {e}")
		# Fallback response
		return {
		    "text": "I'm sorry, I had a little trouble thinking.",
		    "emotion": "neutral"
		}


class TTSRequest(BaseModel):
	text: str
	voice: str


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
	"""
    Accepts text and a voice, returns the generated audio as a WAV file stream.
    """
	try:
		temp_audio_path = "data/temp_tts_output.wav"
		tts.generate(request.text,
		             output_path=temp_audio_path,
		             voice=request.voice)

		# Stream the file back
		with open(temp_audio_path, "rb") as f:
			audio_bytes = f.read()

		return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")
	except Exception as e:
		print(f"TTS Error: {e}")
		raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8001)
	print("Now start the Node server. In a new terminal, run:")
	print("cd app_server")
	print("npm run build # if necessary")
	print("npm start")
