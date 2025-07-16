# adapted from https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/stt/generate.py

from typing import Any
import config as cfg
import os, time
import mlx.core as mx
from mlx_audio.stt.utils import load_model
from mlx_audio.stt.generate import save_as_json, save_as_srt, save_as_txt, save_as_vtt

model: Any


def init(model_path: str = cfg.WHISPER_MODEL):
	global model
	model = load_model(model_path)
	print(f"\n\033[94mModel:\033[0m {model_path}")
	mx.reset_peak_memory()


def unload():
	global model
	if not model:
		return
	del model


def generate(
    audio_path: str,
    output_path: str = '',
    format: str = "txt",
    verbose: bool = True,
):
	global model
	if not model:
		init()

	print(f"\033[94mAudio path:\033[0m {audio_path}")
	if output_path:
		print(f"\033[94mOutput path:\033[0m {output_path}")
	print(f"\033[94mFormat:\033[0m {format}")
	mx.reset_peak_memory()
	start_time = time.time()
	segments = model.generate(audio_path)
	end_time = time.time()

	if verbose:
		print("\n\033[94mTranscription:\033[0m")
		print(segments.text)
		print("\n\033[94mSegments:\033[0m")
		if hasattr(segments, "segments"):
			print(segments.segments)
		elif hasattr(segments, "tokens"):
			print(segments.tokens)
		else:
			print(segments)

	print(f"\033[94mProcessing time:\033[0m {end_time - start_time:.2f} seconds")
	print(f"\033[94mPeak memory:\033[0m {mx.get_peak_memory() / 1e9:.2f} GB")

	if output_path:
		os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

	if format == "txt" and output_path:
		save_as_txt(segments, output_path)
	elif format == "srt" and output_path:
		save_as_srt(segments, output_path)
	elif format == "vtt" and output_path:
		save_as_vtt(segments, output_path)
	elif format == "json" and output_path:
		save_as_json(segments, output_path)

	return segments
