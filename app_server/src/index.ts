import express from 'express';
import http from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import path from 'path';
import fs from 'fs/promises';
import axios from 'axios';
import FormData from 'form-data';

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

const AI_API_URL = 'http://127.0.0.1:8001';
const CHARACTERS_DIR = path.join(__dirname, '../../data/characters');
const FRONTEND_DIR = path.join(__dirname, '../../frontend');

interface Character {
	name: string;
	voice: string;
	images: Record<string, string>;
	instructions?: string; // Our new field for the system prompt
}

interface AppState {
	characters: Record<string, Character>;
	currentCharacterKey: string | null;
	chatHistory: { role: 'user' | 'assistant'; content: string }[];
	isRecording: boolean;
}

const state: AppState = {
	characters: {},
	currentCharacterKey: null,
	chatHistory: [],
	isRecording: false,
};

// --- Character Management ---
async function loadCharacters() {
	try {
		const characterFolders = await fs.readdir(CHARACTERS_DIR);
		for (const charFolder of characterFolders) {
			const configPath = path.join(CHARACTERS_DIR, charFolder, 'config.json');
			try {
				const data = await fs.readFile(configPath, 'utf-8');
				state.characters[charFolder] = JSON.parse(data);
			} catch {
				// Ignore folders without a valid config.json (like .DS_Store)
			}
		}
		if (Object.keys(state.characters).length > 0) {
			state.currentCharacterKey = Object.keys(state.characters)[0];
			console.log(
				`Loaded ${Object.keys(state.characters).length} characters. Default: ${
					state.currentCharacterKey
				}`
			);
		}
	} catch (error) {
		console.error('Error loading characters:', error);
	}
}

function getSystemPrompt(): string {
	if (!state.currentCharacterKey) return 'You are a helpful AI.';
	const char = state.characters[state.currentCharacterKey];
	const valid_emotions = Object.keys(char.images).filter(
		(e) => !['talking', 'listening', 'thinking'].includes(e)
	);

	let prompt = `You are an expressive AI character named ${
		char.name
	}. Respond in a JSON object with keys: "text" (your spoken response) and "emotion" (your current feeling). Valid emotions are: ${valid_emotions.join(
		', '
	)}.`;

	// Add the custom instructions if they exist
	if (char.instructions) {
		prompt += `\n\nIMPORTANT INSTRUCTIONS:\n${char.instructions}`;
	}
	return prompt;
}

// --- WebSocket Logic ---
wss.on('connection', (ws) => {
	console.log('Client connected');

	// Send initial state
	ws.send(
		JSON.stringify({
			type: 'INIT_STATE',
			payload: {
				characters: state.characters,
				currentCharacterKey: state.currentCharacterKey,
				chatHistory: state.chatHistory,
			},
		})
	);

	ws.on('message', async (message) => {
		const { type, payload } = JSON.parse(message.toString());

		switch (type) {
			case 'PROCESS_AUDIO':
				handleAudioProcessing(payload.audio);
				break;
			case 'SWITCH_CHARACTER':
				state.currentCharacterKey = payload.key;
				state.chatHistory = []; // Clear history on character switch
				broadcast({
					type: 'CHARACTER_SWITCHED',
					payload: {
						key: state.currentCharacterKey,
						instructions:
							state.characters[state.currentCharacterKey!]?.instructions || '',
					},
				});
				broadcast({ type: 'CHAT_CLEAR' });
				break;
			case 'SET_INSTRUCTIONS':
				if (state.currentCharacterKey) {
					const char = state.characters[state.currentCharacterKey];
					char.instructions = payload.instructions;
					// Save to config file
					const configPath = path.join(
						CHARACTERS_DIR,
						state.currentCharacterKey,
						'config.json'
					);
					await fs.writeFile(configPath, JSON.stringify(char, null, 2));
					console.log(`Updated instructions for ${char.name}`);
				}
				break;
		}
	});

	ws.on('close', () => console.log('Client disconnected'));
});

function broadcast(message: object) {
	wss.clients.forEach((client) => {
		if (client.readyState === WebSocket.OPEN) {
			client.send(JSON.stringify(message));
		}
	});
}

// --- Core Interaction Logic ---
async function handleAudioProcessing(audioBase64: string) {
	broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Transcribing...' } });
	const audioBuffer = Buffer.from(audioBase64, 'base64');

	try {
		// 1. STT
		const formData = new FormData();
		formData.append('audio_file', audioBuffer, 'audio.wav');

		const sttResponse = await axios.post(`${AI_API_URL}/stt`, formData, {
			headers: {
				...formData.getHeaders(),
			},
		});
		const userText = sttResponse.data.text;
		if (!userText) {
			broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Idle' } });
			return;
		}

		state.chatHistory.push({ role: 'user', content: userText });
		broadcast({
			type: 'CHAT_MESSAGE',
			payload: { role: 'user', content: userText },
		});
		broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Thinking...' } });

		// 2. LLM
		const llmResponse = await axios.post(`${AI_API_URL}/llm`, {
			prompt: userText,
			system_prompt: getSystemPrompt(),
		});
		const { text: aiText, emotion } = llmResponse.data;

		state.chatHistory.push({ role: 'assistant', content: aiText });
		broadcast({
			type: 'CHAT_MESSAGE',
			payload: { role: 'assistant', content: aiText, emotion },
		});
		broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Speaking...' } });

		// 3. TTS
		const ttsResponse = await axios.post(
			`${AI_API_URL}/tts`,
			{
				text: aiText,
				voice:
					state.characters[state.currentCharacterKey!]?.voice || 'af_heart',
			},
			{ responseType: 'arraybuffer' }
		);

		const audioData = Buffer.from(ttsResponse.data, 'binary').toString(
			'base64'
		);
		broadcast({ type: 'PLAY_AUDIO', payload: { audio: audioData } });

		// Status will be set back to Idle on the frontend after audio finishes playing
	} catch (error: any) {
		if (error.response) {
			console.error('Error in processing chain:', error.response.data);
		} else {
			console.error('Error in processing chain:', error.message);
		}
		broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Error' } });
		setTimeout(
			() => broadcast({ type: 'STATUS_UPDATE', payload: { status: 'Idle' } }),
			2000
		);
	}
}

// --- Server Setup ---
app.use(express.static(FRONTEND_DIR));
app.use(express.static(path.join(__dirname, '../../')));

server.listen(8000, async () => {
	await loadCharacters();
	console.log('Server listening on http://localhost:8000');
});
