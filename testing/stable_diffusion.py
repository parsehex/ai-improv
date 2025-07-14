import config as cfg
from stable_diffusion_cpp import StableDiffusion

# adapted from README:


def callback(step: int, steps: int, time: float):
	print("Completed step: {} of {}".format(step, steps))


stable_diffusion = StableDiffusion(
    model_path=cfg.IMAGE_MODEL,
    verbose=False,
    # wtype="default", # Weight type (e.g. "q8_0", "f16", etc) (The "default" setting is automatically applied and determines the weight type of a model file)
)
output = stable_diffusion.txt_to_img(
    prompt="a lovely cat",
    width=512,  # Must be a multiple of 64
    height=512,  # Must be a multiple of 64
    progress_callback=callback,  # Must have Verbose=True for this to fire
    sample_steps=10,
    # seed=1337, # Uncomment to set a specific seed (use -1 for a random seed)
)
output[0].save("./data/test.png")  # Output returned as list of PIL Images
