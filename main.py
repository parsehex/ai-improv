# write_transcript_live.py - Uses WhisperLive
# 	Listens to microphone, writes a rolling transcript of the last e.g. 5 lines of transcript to ./data/live_transcript_output.txt
# lib/tts.py - Uses mlx-audio / Kokoro TTS
# 	Generate TTS audio
# lib/llm.py - Uses llama-cpp-python
# 	Generate chat completion
# testing/stable_diffusion.py
# 	Example generating image. Too slow on my macbook, will pre-generate on desktop

# My goal with this is to orchestrate an experience being able to interact with a virtual character with speech alone.
# A separate app called Vuo is (will be) used to render the character's image on screen as well as displaying e.g. transcription text on-screen.
# The app displays the content of certain files every frame (e.g. character image, transcript .txt file), which are updated by this python app.
# Character Images
# 	A character's appearance is described, multiple images are generated with that description with different emotions / states (e.g. talking).
#  The current image/state is fed to the LLM and it's able to call a tool/function to change to a new image, which swaps out the image that Vuo renders on-screen.
# At some kind of interval and/or activity, send the current chunk of transcript to the LLM to get a response
# 	-> Generate & Play TTS

# I think we'll probably write the character's (spoken) response to display as well as the user's, at least for debug purposes.

# LLM (system) prompt notes
# 	- instruct to respond with relevant dialogue which is of an appropriate length given the context
# 	- include incomplete latest transcript segment when available, but designate as "tentative" + (dynamically/conditionally) provide instructions/explanation
