import os
import json
from stable_diffusion_cpp import StableDiffusion
import config as cfg

# --- Config ---
CHARACTER_NAME = "Luna"
BASE_PROMPT = "a futuristic digital assistant girl named Luna, anime style, portrait, looking at viewer"
EMOTIONS = [
    "neutral", "happy", "thinking", "talking", "surprised", "listening"
]
OUTPUT_DIR = "./data/character_images"
IMAGE_MAP_FILE = "./data/character_images/available_images.json"


def ensure_dir(path):
	os.makedirs(path, exist_ok=True)


def generate_images():
	ensure_dir(OUTPUT_DIR)
	sd = StableDiffusion(model_path=cfg.IMAGE_MODEL, verbose=False)

	image_map = {}

	for emotion in EMOTIONS:
		prompt = f"{BASE_PROMPT}, {emotion} expression"
		output = sd.txt_to_img(prompt=prompt,
		                       width=512,
		                       height=512,
		                       sample_steps=15)

		filename = f"{CHARACTER_NAME.lower()}_{emotion}.png"
		output_path = os.path.join(OUTPUT_DIR, filename)
		output[0].save(output_path)
		image_map[emotion] = output_path
		print(f"Generated: {filename}")

	# Save image map for app use
	with open(IMAGE_MAP_FILE, 'w') as f:
		json.dump(image_map, f, indent=2)
	print(f"Image map saved to {IMAGE_MAP_FILE}")


if __name__ == "__main__":
	generate_images()
