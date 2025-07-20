import io
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import soundfile as sf
import numpy as np
import ffmpeg
import os

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
	print("Now start the Node server. In a new terminal, run:")
	print("cd app_server")
	print("npm run build # if necessary")
	print("npm start")


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
    Accepts an audio file, converts it to a standard WAV format,
    and returns the transcribed text.
    """
	# Define temporary paths. Using the original filename helps keep track.
	temp_input_path = f"data/temp_input_{audio_file.filename}"
	temp_output_path = "data/temp_stt_input.wav"

	try:
		# 1. Save the uploaded file (e.g., .webm) to a temporary location.
		with open(temp_input_path, "wb") as f:
			f.write(await audio_file.read())

		# 2. Use ffmpeg to convert the input file to a 16kHz mono WAV file.
		print(f"Converting '{temp_input_path}' to '{temp_output_path}'...")
		(ffmpeg.input(temp_input_path).output(
		    temp_output_path,
		    ac=1,  # Mono channel
		    ar='16000',  # 16kHz sample rate
		    format='wav').run(overwrite_output=True, quiet=True))
		print("Conversion complete.")

		# 3. Pass the *converted* WAV file to the STT function.
		result = stt.generate(temp_output_path, verbose=False)
		return {"text": result.text.strip()}

	except ffmpeg.Error as e:
		# Provide more specific feedback if ffmpeg fails
		error_details = e.stderr.decode() if e.stderr else str(e)
		print(f"ffmpeg error: {error_details}")
		raise HTTPException(status_code=500,
		                    detail=f"Audio conversion failed: {error_details}")
	except Exception as e:
		print(f"STT Error: {e}")
		raise HTTPException(status_code=500, detail=str(e))
	finally:
		# 4. Clean up both temporary files.
		if os.path.exists(temp_input_path):
			os.remove(temp_input_path)
		if os.path.exists(temp_output_path):
			os.remove(temp_output_path)


class LLMRequest(BaseModel):
	prompt: str
	system_prompt: str


@app.post("/llm")
async def language_model_generate(request: LLMRequest):
	"""
    Accepts a user prompt and system prompt, and streams the model's response.
    """
	try:
		# The generator for the streaming response
		def stream_generator():
			try:
				for chunk in llm.generate_stream(request.prompt,
				                                 sys_input=request.system_prompt,
				                                 json=True):
					yield chunk
			except Exception as e:
				print(f"LLM stream error: {e}")
				# The stream will simply end here. The client needs to handle it.
				pass

		return StreamingResponse(stream_generator(), media_type="text/plain")

	except Exception as e:
		print(f"LLM Error before stream start: {e}")
		# This will catch errors before the stream starts (e.g., model not loaded)
		raise HTTPException(
		    status_code=500,
		    detail=json.dumps({
		        "text": "I'm sorry, I had a little trouble starting to think.",
		        "emotion": "neutral"
		    }))


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
