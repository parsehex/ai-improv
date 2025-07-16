import json
import os
from stable_diffusion_cpp import StableDiffusion
import config as cfg

CHARACTER_NAME = "Luna"
BASE_PROMPT = f"a digital illustration of a friendly AI character named {CHARACTER_NAME}"
OUTPUT_DIR = "./data/character_images/"
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

	mapping = {}
	charname = CHARACTER_NAME.lower()
	for key, detail in EMOTIONS.items():
		full_prompt = f"{BASE_PROMPT}, {key} expression, {detail}"
		print(f"Generating: {key} => {full_prompt}")

		images = sd.txt_to_img(prompt=full_prompt,
		                       width=512,
		                       height=512,
		                       sample_steps=25,
		                       seed=-1)

		filename = f"{charname}_{key}.png"
		filepath = os.path.join(OUTPUT_DIR, filename)
		images[0].save(filepath)
		mapping[key] = filepath

	with open(os.path.join(OUTPUT_DIR, "available_images.json"), "w") as f:
		json.dump(mapping, f, indent=2)

	print("Character images generated and mapping saved.")


if __name__ == "__main__":
	generate_images()
