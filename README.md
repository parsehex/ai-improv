# AI Improv

This is an experiment to allow for interacting with AI-powered characters via end-to-end speech.

There are 3 different versions of this + a script for displaying the state in a window (pygame).

Much of the code was generated with Google Gemini 2.5 Pro, using my [TaskMate](https://github.com/parsehex/TaskMate) app for constructing prompts to send with the appropriate context.

## `main_live.py` (unstable, not finished)

My first try, this continuously transcribes audio from the microphone and gets a response after a period of silence. TTS and images are not implemented.

To use this:

- In Terminal 1 (or on separate machine), run `python run_whisper_server.py`
- Ensure that `config.py` is setup.
  - `WHISPER_SERVER_IP` should point to the machine used above.
  - `STORY_MODEL_*` options are not used.
- In Terminal 2, run `python main_live.py`
- Start the Vuo renderer app (not included)

## `main_manual.py`

Second iteration after realizing that the rolling transcript wasn't good quality + the UX was clunky, I decided to do it more manually by having the user hold a button to record. This turned out to be a nicer experience.

To use this:

- Ensure that `config.py` is setup.
  - `WHISPER_SERVER_*` and `STORY_MODEL_*` options are not used.
- In Terminal 1, run `python main_manual.py`
- In Terminal 2, run `python main_display.py`

## `main_web.py`

Third iteration to add a web-based remote control. This way, a smartphone or other device can be used to trigger the character to 'listen' without it being quite as obvious. Also, managing the app's state from the web remote.

To use this:

- Ensure that `config.py` is setup.
  - `WHISPER_SERVER_*` and `STORY_MODEL_*` options are not used.
- In Terminal 1, run `python main_web.py`
- In Terminal 2, run `python main_display.py`
- The remote is available at <http://localhost:8000>

## `run_app.py`

A wrapper script to run `main_web.py` and `main_display.py` together, allowing for restarting `main_web` while keeping the pygame window open.

## `story_app/`

This is a separate demo which I haven't kept working on.
