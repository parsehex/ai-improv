import subprocess
import sys
import time
import os

# --- Configuration ---
# Use sys.executable to ensure we use the same python interpreter
# (and virtual environment) that is running this script.
PYTHON_EXECUTABLE = sys.executable
WEB_APP_SCRIPT = "main_web.py"
DISPLAY_APP_SCRIPT = "main_display.py"


class ProcessManager:
	"""A simple class to manage the web and display subprocesses."""

	def __init__(self):
		self.processes = {"web": None, "display": None}
		# Ensure data directory exists to prevent file-not-found on first run
		os.makedirs("./data", exist_ok=True)

	def is_running(self, name: str) -> bool:
		"""Check if a process is active."""
		proc = self.processes.get(name)
		return proc and proc.poll() is None

	def start_process(self, name: str, script_path: str):
		"""Starts a script as a subprocess if not already running."""
		if self.is_running(name):
			print(f"[{name.capitalize()}] process is already running.")
			return

		print(f"Starting [{name.capitalize()}] process...")
		# We use subprocess.Popen for non-blocking execution.
		# This allows our manager script to continue running and accept commands.
		try:
			proc = subprocess.Popen([PYTHON_EXECUTABLE, script_path])
			self.processes[name] = proc
			time.sleep(2)  # Give it a moment to initialize
			if not self.is_running(name):
				print(
				    f"Error: [{name.capitalize()}] process failed to start or exited immediately.",
				    file=sys.stderr)
				self.processes[name] = None
			else:
				print(f"[{name.capitalize()}] process started with PID: {proc.pid}")
		except FileNotFoundError:
			print(
			    f"Error: Script not found at '{script_path}'. Make sure you are in the correct directory.",
			    file=sys.stderr)
		except Exception as e:
			print(f"An unexpected error occurred while starting [{name}]: {e}",
			      file=sys.stderr)

	def stop_process(self, name: str):
		"""Stops a running subprocess."""
		if not self.is_running(name):
			print(f"[{name.capitalize()}] process is not running.")
			return

		print(f"Stopping [{name.capitalize()}] process...")
		proc = self.processes[name]
		proc.terminate()  # Graceful shutdown
		try:
			proc.wait(timeout=5)  # Wait up to 5 seconds
			print(f"[{name.capitalize()}] process stopped.")
		except subprocess.TimeoutExpired:
			print(
			    f"[{name.capitalize()}] did not terminate gracefully, forcing kill.")
			proc.kill()  # Forceful shutdown
			print(f"[{name.capitalize()}] process killed.")
		finally:
			self.processes[name] = None

	def restart_web_app(self):
		"""Convenience method to restart the web application."""
		print("-" * 20)
		self.stop_process("web")
		time.sleep(1)  # Give OS a moment to release ports/resources
		self.start_process("web", WEB_APP_SCRIPT)
		print("-" * 20)

	def run_console(self):
		"""The main interactive loop for the user."""
		# Initial startup
		self.start_process("display", DISPLAY_APP_SCRIPT)
		self.start_process("web", WEB_APP_SCRIPT)

		try:
			while True:
				print("\n--- AI Improv Control Console ---")
				print(" (r) Restart Web App")
				print(" (s) Stop Web App")
				print(" (w) Start Web App (if stopped)")
				print(" (q) Quit All")

				# Check status of processes
				web_status = "Running" if self.is_running("web") else "Stopped"
				display_status = "Running" if self.is_running("display") else "Stopped"
				print(f" Status: [Web: {web_status}] [Display: {display_status}]")

				choice = input("Enter command: ").lower().strip()

				if choice == 'r':
					self.restart_web_app()
				elif choice == 's':
					self.stop_process("web")
				elif choice == 'w':
					self.start_process("web", WEB_APP_SCRIPT)
				elif choice == 'q':
					break
				else:
					print("Invalid command.")
		finally:
			print("\nShutting down all processes...")
			self.stop_process("web")
			self.stop_process("display")
			print("Cleanup complete. Exiting.")


if __name__ == "__main__":
	manager = ProcessManager()
	manager.run_console()
