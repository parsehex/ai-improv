import pyttsx3

engine = pyttsx3.init()
engine.save_to_file('Hello world.', './data/output-pyttsx3.mp3')
engine.runAndWait()
