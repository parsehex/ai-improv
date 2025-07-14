import config as cfg
from f5_tts_mlx.generate import generate

audio = generate(generation_text='Hello world.',
                 output_path='./data/output-q8_0.wav',
                 quantization_bits=4)
