from llama_cpp import Llama
from openai.types.chat import ChatCompletion
import config as cfg

model: Llama


def init(model_path=cfg.LANGUAGE_MODEL):
	global model
	model = Llama(
	    model_path,
	    n_gpu_layers=-1,  # Uncomment to use GPU acceleration
	    # seed=1337, # Uncomment to set a specific seed
	    # n_ctx=2048, # Uncomment to increase the context window
	    verbose=False)


def unload():
	global model
	if not model:
		return
	model.close()
	del model


def generate(input: str):
	global model
	if not model:
		init()

	output = model.create_chat_completion_openai_v1(
	    messages=[
	        # {'role': 'system', 'content': 'The following is '}
	        {
	            'role': 'user',
	            'content': input
	        }
	    ],
	    max_tokens=32,
	    stop=["Q:", "\n"],
	    stream=False)
	assert isinstance(output, ChatCompletion)

	output_str = output.choices[0].message.content
	assert output_str is not None
	return output_str
