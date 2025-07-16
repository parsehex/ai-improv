import json
import os
from stable_diffusion_cpp import StableDiffusion
import config as cfg

# --- Character Configuration ---
# Change these values to generate a new character
CHARACTER_NAME = "Luna"
CHARACTER_VOICE = "af_heart"  # A voice from the list in lib/tts.py
# --- End Configuration ---

BASE_PROMPT = f"a digital illustration of a friendly AI character named {CHARACTER_NAME}"
OUTPUT_DIR = os.path.join("./data/characters/", CHARACTER_NAME.lower())
EMOTIONS = {
    "neutral": "with a calm expression",
    "happy": "smiling warmly",
    "thinking": "looking contemplative, hand on chin",
    "talking": "speaking mid-sentence",
    "surprised": "with wide eyes, slightly shocked",
    "listening": "attentively listening, leaning forward"
}


def generate_images():
	os.makedirs(OUTPUT_DIR, exist_ok=True)
	sd = StableDiffusion(model_path=cfg.IMAGE_MODEL, verbose=False)

	image_mapping = {}
	charname_lower = CHARACTER_NAME.lower()
	for key, detail in EMOTIONS.items():
		full_prompt = f"{BASE_PROMPT}, {key} expression, {detail}"
		print(f"Generating: {key} => {full_prompt}")

		images = sd.txt_to_img(prompt=full_prompt,
		                       width=512,
		                       height=512,
		                       sample_steps=25,
		                       seed=-1)

		filename = f"{charname_lower}_{key}.png"
		# Save image inside the character's specific directory
		filepath = os.path.join(OUTPUT_DIR, filename)
		images[0].save(filepath)
		# Store the relative path for the config
		image_mapping[key] = filepath

	character_config = {
	    "name": CHARACTER_NAME,
	    "voice": CHARACTER_VOICE,
	    "images": image_mapping
	}

	config_path = os.path.join(OUTPUT_DIR, "config.json")
	with open(config_path, "w") as f:
		json.dump(character_config, f, indent=2)

	print(
	    f"\nCharacter '{CHARACTER_NAME}' generated and config saved to {config_path}"
	)


if __name__ == "__main__":
	generate_images()
