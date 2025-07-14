from mlx.nn import Module
import config as cfg
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model
import soundfile as sf

model: Module
pipeline: KokoroPipeline


def init():
	global model, pipeline
	model = load_model(cfg.TTS_MODEL)
	pipeline = KokoroPipeline(lang_code='a', model=model, repo_id=cfg.TTS_MODEL)


def generate(text: str, output_path='audio.wav'):
	global pipeline
	if not pipeline:
		init()

	for _, _, audio in pipeline(text,
	                            voice='af_heart',
	                            speed=1,
	                            split_pattern=r'\n+'):
		assert audio is not None
		sf.write(output_path, audio[0], 24000)
