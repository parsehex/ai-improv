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


def generate(input: str, sys_input='', json=False):
	global model
	if not model:
		init()

	messages = [{'role': 'user', 'content': input}]
	if sys_input:
		msg = {'role': 'system', 'content': sys_input}
		messages.insert(0, msg)

	kwargs = {
	    'messages': messages,
	    'max_tokens': 128,
	    'stop': ["Q:", "\n"],
	    'stream': False
	}
	if json:
		kwargs['response_format'] = {'type': 'json_object'}

	output = model.create_chat_completion_openai_v1(**kwargs)
	assert isinstance(output, ChatCompletion)

	output_str = output.choices[0].message.content
	assert output_str is not None
	return output_str
