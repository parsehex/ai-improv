import argparse
from llama_cpp import Llama
from openai.types.chat import ChatCompletion

# --- PROMPT ENGINEERING ---
# These prompts define the "brains" of our multi-step process.

PLANNING_PROMPT_TEMPLATE = """
You are an expert storyteller and plot designer. Your task is to create a detailed, structured plan for a story based on the user's request.

The plan should be comprehensive and provide a clear roadmap for writing the full story. Do NOT write the story itself, only the plan.

Structure your plan with the following sections:
1.  **Core Concept:** A one-sentence summary of the story.
2.  **Characters:** Brief descriptions of the main protagonist, antagonist, and any key supporting characters.
3.  **Setting:** Describe the time, place, and mood of the story's world.
4.  **Plot Outline (Three-Act Structure):**
    *   **Act 1 (The Setup):** Introduction to the protagonist and their world. The inciting incident that kicks off the story.
    *   **Act 2 (The Confrontation):** Rising action, challenges, and the midpoint where the stakes are raised.
    *   **Act 3 (The Resolution):** The climax, falling action, and the final resolution.
5.  **Key Themes:** The central ideas or messages the story will explore.

Here is the user's request:
---
{user_prompt}
---
"""

WRITING_PROMPT_TEMPLATE = """
You are a master fiction writer. Your task is to write a complete, engaging short story based on the provided plan and the original user request.

Follow the plan closely to ensure all key plot points, character arcs, and themes are included. Write in a compelling narrative style, using vivid descriptions, strong character voices, and emotional depth.

This is the original user request for context:
---
{user_prompt}
---

This is the detailed story plan you must follow:
--- STORY PLAN ---
{story_plan}
--- END OF PLAN ---

Now, write the full, captivating story.
"""


def generate_story_plan(llm: Llama, user_prompt: str) -> str:
	"""
    Generates a structured story plan using the LLM.

    Args:
        llm: An initialized Llama object.
        user_prompt: The user's initial story idea.

    Returns:
        A string containing the generated story plan.
    """
	print(">>> Stage 1: Generating story plan...")

	# We use a system prompt to set the role and a user prompt for the task
	messages = [{
	    "role": "system",
	    "content": "You are an expert storyteller and plot designer."
	}, {
	    "role":
	    "user",
	    "content":
	    PLANNING_PROMPT_TEMPLATE.format(user_prompt=user_prompt)
	}]

	response = llm.create_chat_completion_openai_v1(
	    messages=messages,
	    max_tokens=1024,  # Allow enough tokens for a detailed plan
	    temperature=0.7,
	)
	assert isinstance(response, ChatCompletion)
	assert response.choices[0].message.content

	plan = response.choices[0].message.content.strip()
	print("...Plan generated successfully.\n")
	return plan


def generate_story_from_plan(llm: Llama, user_prompt: str,
                             story_plan: str) -> str:
	"""
    Generates the full story based on the provided plan.

    Args:
        llm: An initialized Llama object.
        user_prompt: The user's original story idea.
        story_plan: The plan generated in the first stage.

    Returns:
        A string containing the final story.
    """
	print(">>> Stage 2: Writing the full story from the plan...")

	messages = [{
	    "role": "system",
	    "content": "You are a master fiction writer."
	}, {
	    "role":
	    "user",
	    "content":
	    WRITING_PROMPT_TEMPLATE.format(user_prompt=user_prompt,
	                                   story_plan=story_plan)
	}]

	response = llm.create_chat_completion_openai_v1(
	    messages=messages,
	    max_tokens=4096,  # Allow more tokens for the full story
	    temperature=0.8,  # Slightly higher temp for more creative writing
	)
	assert isinstance(response, ChatCompletion)
	assert response.choices[0].message.content

	story = response.choices[0].message.content.strip()
	print("...Story generation complete.\n")
	return story


def main():
	"""Main function to run the story generation script."""
	parser = argparse.ArgumentParser(
	    description="Generate a story in a multi-step process using a local LLM.",
	    formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument("-m",
	                    "--model",
	                    required=True,
	                    help="Path to the GGUF model file.")
	parser.add_argument(
	    "prompt_file", help="Path to the text file containing the story prompt.")
	parser.add_argument("-c",
	                    "--n_ctx",
	                    type=int,
	                    default=8192,
	                    help="Context size for the model (default: 8192).")
	args = parser.parse_args()

	# --- 1. Load the LLM ---
	print(f"Loading model from: {args.model}")

	try:
		llm = Llama(model_path=args.model,
		            n_gpu_layers=-1,
		            n_ctx=args.n_ctx,
		            verbose=False)
	except Exception as e:
		print(f"Error loading model: {e}")
		return

	# --- 2. Read the user's prompt from the file ---
	try:
		with open(args.prompt_file, 'r', encoding='utf-8') as f:
			user_prompt = f.read().strip()
	except FileNotFoundError:
		print(f"Error: Prompt file not found at '{args.prompt_file}'")
		return
	except Exception as e:
		print(f"Error reading prompt file: {e}")
		return

	print(
	    f"--- Using Initial Prompt ---\n{user_prompt}\n---------------------------\n"
	)

	# --- 3. Execute the multi-step generation process ---
	story_plan = generate_story_plan(llm, user_prompt)

	print("--- Generated Story Plan ---")
	print(story_plan)
	print("--------------------------\n")

	final_story = generate_story_from_plan(llm, user_prompt, story_plan)

	print("--- Final Generated Story ---")
	print(final_story)
	print("---------------------------\n")

	# --- 4. Save the output to a file ---
	with open("generated_story.txt", "w", encoding='utf-8') as f:
		f.write("--- INITIAL PROMPT ---\n")
		f.write(user_prompt + "\n\n")
		f.write("--- GENERATED STORY PLAN ---\n")
		f.write(story_plan + "\n\n")
		f.write("--- FINAL STORY ---\n")
		f.write(final_story + "\n")
	print("Story and plan have been saved to 'generated_story.txt'")


if __name__ == "__main__":
	main()
