from llama_cpp import Llama
from openai.types.chat import ChatCompletion
import config as cfg

llm: Llama


def init():
	global llm
	llm = Llama(
	    model_path=cfg.LANGUAGE_MODEL,
	    n_gpu_layers=-1,  # Uncomment to use GPU acceleration
	    # seed=1337, # Uncomment to set a specific seed
	    # n_ctx=2048, # Uncomment to increase the context window
	    verbose=False)


def generate(input: str):
	global llm
	if not llm:
		init()

	output = llm.create_chat_completion_openai_v1(
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
