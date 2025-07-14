import config as cfg
from mlx_audio.stt.generate import generate

# record some audio
audio_path = './data/output.wav'

generate(cfg.WHISPER_MODEL,
         audio_path=audio_path,
         output_path='./data/output-wav.txt')
