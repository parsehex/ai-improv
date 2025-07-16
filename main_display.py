from lib.display import Display
import sys

if __name__ == "__main__":
	print("Starting AI Improv Display...")
	print("This window will reflect the state of the main application.")
	print("Run main_web.py (or another main script) in a separate terminal.")
	print("Close the Pygame window or press Ctrl+C here to stop.")

	try:
		display_app = Display()
		display_app.run()
	except KeyboardInterrupt:
		print("\nDisplay shut down by user.")
	except Exception as e:
		print(f"\nAn error occurred: {e}", file=sys.stderr)
	finally:
		print("Display stopped.")
