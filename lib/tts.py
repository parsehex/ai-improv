from mlx.nn import Module
import config as cfg
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model
import soundfile as sf

model: Module
pipeline: KokoroPipeline


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


def generate(text: str, output_path='audio.wav'):
	global pipeline
	if not pipeline:
		init()

	for _, _, audio in pipeline(text,
	                            voice='af_heart',
	                            speed=1.2,
	                            split_pattern=r'\n+'):
		assert audio is not None
		sf.write(output_path, audio[0], 24000)
