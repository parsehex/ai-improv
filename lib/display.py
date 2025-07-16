import pygame
import os
import time

# --- File paths (mirroring your main app) ---
LLM_INPUT_FILE = "./data/llm_input.txt"
LLM_OUTPUT_FILE = "./data/llm_output.txt"
CURRENT_IMAGE_PATH = "./data/current_character_image.png"
APP_STATE_FILE = "./data/app_state.txt"

# --- Display Configuration ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
BACKGROUND_COLOR = (20, 20, 40)  # Dark blue-ish
TEXT_COLOR = (230, 230, 230)  # Off-white
HEADER_COLOR = (150, 150, 200)  # Lavender
IMAGE_POSITION = (450, 50)
IMAGE_MAX_SIZE = (300, 450)
TEXT_AREA_WIDTH = 400
TEXT_START_X = 30
TEXT_START_Y = 50


class Display:
	"""
    Manages the Pygame window for displaying character, input, and output.
    It works by polling the data files for changes, similar to the Vuo setup.
    """

	def __init__(self):
		pygame.init()
		self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
		pygame.display.set_caption("AI Improv Display")
		self.clock = pygame.time.Clock()

		# --- Fonts ---
		self.header_font = pygame.font.Font(None, 42)
		self.body_font = pygame.font.Font(None, 28)

		# --- State ---
		self.user_text = ""
		self.ai_text = ""
		self.character_image = None
		self.running = False
		self.app_state = "Idle"

		# --- File Watching ---
		# Store last modification times to avoid reloading unchanged files
		self._file_mtimes = {}

	def _read_file_if_changed(self, path: str) -> str | None:
		"""Reads file content only if it has been modified since last read."""
		try:
			mtime = os.path.getmtime(path)
			if path not in self._file_mtimes or mtime > self._file_mtimes[path]:
				self._file_mtimes[path] = mtime
				with open(path, 'r', encoding='utf-8') as f:
					return f.read()
		except FileNotFoundError:
			# First run, file might not exist yet.
			self._file_mtimes[path] = 0
		except Exception as e:
			print(f"Error reading {path}: {e}")
		return None

	def _load_image_if_changed(self, path: str) -> pygame.Surface | None:
		"""Loads the character image if it has been modified."""
		try:
			mtime = os.path.getmtime(path)
			if path not in self._file_mtimes or mtime > self._file_mtimes[path]:
				self._file_mtimes[path] = mtime
				# Load the image and scale it to fit within the max dimensions
				img = pygame.image.load(path).convert_alpha()
				img_rect = img.get_rect()
				scale = min(IMAGE_MAX_SIZE[0] / img_rect.width,
				            IMAGE_MAX_SIZE[1] / img_rect.height)
				new_size = (int(img_rect.width * scale), int(img_rect.height * scale))
				return pygame.transform.smoothscale(img, new_size)
		except (pygame.error, FileNotFoundError):
			# This can happen if the file is being written while we try to read it
			return None
		except Exception as e:
			print(f"Error loading image {path}: {e}")
		return None

	def _wrap_text(self, text: str, font: pygame.font.Font,
	               max_width: int) -> list[str]:
		"""Wraps text to fit within a maximum width."""
		lines = []
		words = text.split(' ')
		current_line = ""
		for word in words:
			test_line = f"{current_line} {word}".strip()
			if font.size(test_line)[0] <= max_width:
				current_line = test_line
			else:
				lines.append(current_line)
				current_line = word
		lines.append(current_line)
		return lines

	def update_state(self):
		"""Polls files for changes and updates the display state."""
		new_app_state = self._read_file_if_changed(APP_STATE_FILE)
		if new_app_state is not None:
			self.app_state = new_app_state.strip()

		# Update text
		new_user_text = self._read_file_if_changed(LLM_INPUT_FILE)
		if new_user_text is not None:
			self.user_text = new_user_text.strip()

		new_ai_text = self._read_file_if_changed(LLM_OUTPUT_FILE)
		if new_ai_text is not None:
			self.ai_text = new_ai_text.strip()

		# Update image
		new_image = self._load_image_if_changed(CURRENT_IMAGE_PATH)
		if new_image:
			self.character_image = new_image

	def draw(self):
		"""Renders the current state to the screen."""
		self.screen.fill(BACKGROUND_COLOR)

		if self.app_state == "Offline":
			offline_font = pygame.font.Font(None, 60)
			offline_surf = offline_font.render("System Offline", True, (200, 50, 50))
			offline_rect = offline_surf.get_rect(center=(WINDOW_WIDTH // 2,
			                                             WINDOW_HEIGHT // 2))
			self.screen.blit(offline_surf, offline_rect)
			pygame.display.flip()
			return  # Don't draw anything else

		# --- Draw Character Image ---
		if self.character_image:
			# Center the image within its designated area
			img_rect = self.character_image.get_rect(topleft=IMAGE_POSITION)
			self.screen.blit(self.character_image, img_rect)

		# --- Draw Text ---
		current_y = TEXT_START_Y

		# User Input
		header_surf = self.header_font.render("You Said:", True, HEADER_COLOR)
		self.screen.blit(header_surf, (TEXT_START_X, current_y))
		current_y += 50

		user_lines = self._wrap_text(self.user_text, self.body_font,
		                             TEXT_AREA_WIDTH)
		for line in user_lines:
			line_surf = self.body_font.render(line, True, TEXT_COLOR)
			self.screen.blit(line_surf, (TEXT_START_X, current_y))
			current_y += self.body_font.get_height()

		# AI Output
		current_y += 50  # Add spacing
		header_surf = self.header_font.render("Character Replied:", True,
		                                      HEADER_COLOR)
		self.screen.blit(header_surf, (TEXT_START_X, current_y))
		current_y += 50

		ai_lines = self._wrap_text(self.ai_text, self.body_font, TEXT_AREA_WIDTH)
		for line in ai_lines:
			line_surf = self.body_font.render(line, True, TEXT_COLOR)
			self.screen.blit(line_surf, (TEXT_START_X, current_y))
			current_y += self.body_font.get_height()

		pygame.display.flip()

	def run(self):
		"""The main loop of the display window."""
		self.running = True
		# Initial load
		self.update_state()

		while self.running:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					self.running = False

			self.update_state()
			self.draw()
			self.clock.tick(15)  # Poll for file changes 15 times/sec is plenty

		pygame.quit()
