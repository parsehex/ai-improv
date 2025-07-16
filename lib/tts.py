from mlx.nn import Module
import config as cfg
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model
import soundfile as sf

model: Module
pipeline: KokoroPipeline

# list is from https://huggingface.co/prince-canuma/Kokoro-82M/tree/main/voices
Voices = [
    'af_alloy', 'af_aoede', 'af_bella', 'af_heart', 'af_jessica', 'af_kore',
    'af_nicole', 'af_nova', 'af_river', 'af_sarah', 'af_sky', 'am_adam',
    'am_echo', 'am_eric', 'am_fenrir', 'am_liam', 'am_michael', 'am_onyx',
    'am_puck', 'am_santa'
]


def init(model_path=cfg.TTS_MODEL):
	global model, pipeline
	model = load_model(model_path)
	pipeline = KokoroPipeline(lang_code='a', model=model, repo_id=cfg.TTS_MODEL)


def unload():
	global model, pipeline
	if not model:
		return
	del pipeline
	del model


def generate(text: str,
             output_path='audio.wav',
             voice='af_heart',
             speed=Number(1.2)):
	global pipeline
	if not pipeline:
		init()

	for _, _, audio in pipeline(text,
	                            voice=voice,
	                            speed=speed,
	                            split_pattern=r'\n+'):
		assert audio is not None
		sf.write(output_path, audio[0], 24000)
