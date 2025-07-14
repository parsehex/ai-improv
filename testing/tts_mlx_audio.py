from mlx.nn import Module
import config as cfg
from mlx_audio.tts.generate import generate_audio
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model
import soundfile as sf

generate_audio(
    text=("Hello world."),
    model_path=cfg.TTS_MODEL,
    voice="af_heart",
    # speed=1.2,
    # lang_code="a", # Kokoro: (a)f_heart, or comment out for auto
    file_prefix="data/output-mlx_audio",
    audio_format="wav",
    sample_rate=24000,
    join_audio=True,
    verbose=True  # Set to False to disable print messages
)

# Initialize the model
model_id = 'prince-canuma/Kokoro-82M'
model: Module
pipeline: KokoroPipeline


def init():
	global model, pipeline
	model = load_model(model_id)
	pipeline = KokoroPipeline(lang_code='a', model=model, repo_id=model_id)


def generate(text: str, output_path='audio.wav'):
	for _, _, audio in pipeline(text,
	                            voice='af_heart',
	                            speed=1,
	                            split_pattern=r'\n+'):
		assert audio is not None
		sf.write(output_path, audio[0], 24000)
