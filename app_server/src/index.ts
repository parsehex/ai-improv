import express from 'express';
import http from 'http';
import https from 'https';
import { WebSocketServer, WebSocket } from 'ws';
import path from 'path';
import fs from 'fs';
import fsp from 'fs/promises';
import axios from 'axios';
import FormData from 'form-data';

const app = express();

const HTTP_PORT = 8000;
const HTTPS_PORT = 8443; // Use a different port for the secure server

const AI_API_URL = 'http://127.0.0.1:8001';
const CHARACTERS_DIR = path.join(__dirname, '../../data/characters');
const FRONTEND_DIR = path.join(__dirname, '../../frontend');
const CERTS_DIR = path.join(__dirname, '../certs');

interface Character {
	name: string;
	voice: string;
	images: Record<string, string>;
	instructions?: string;
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

// --- Character Management (no changes) ---
async function loadCharacters() {
	try {
		const characterFolders = await fsp.readdir(CHARACTERS_DIR);
		for (const charFolder of characterFolders) {
			const configPath = path.join(CHARACTERS_DIR, charFolder, 'config.json');
			try {
				const data = await fsp.readFile(configPath, 'utf-8');
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

	if (char.instructions) {
		prompt += `\n\nIMPORTANT INSTRUCTIONS:\n${char.instructions}`;
	}
	return prompt;
}

// --- WebSocket Logic (no changes) ---
// This function will be called later to attach the logic to the correct server
function setupWebSocketLogic(wss: WebSocketServer) {
	wss.on('connection', (ws) => {
		console.log('Client connected');
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
					// Pass the fileName from the payload to the handler
					handleAudioProcessing(wss, payload.audio, payload.fileName);
					break;
				case 'SWITCH_CHARACTER':
					state.currentCharacterKey = payload.key;
					state.chatHistory = [];
					broadcast(wss, {
						type: 'CHARACTER_SWITCHED',
						payload: {
							key: state.currentCharacterKey,
							instructions:
								state.characters[state.currentCharacterKey!]?.instructions ||
								'',
						},
					});
					broadcast(wss, { type: 'CHAT_CLEAR' });
					break;
				case 'SET_INSTRUCTIONS':
					if (state.currentCharacterKey) {
						const char = state.characters[state.currentCharacterKey];
						char.instructions = payload.instructions;
						const configPath = path.join(
							CHARACTERS_DIR,
							state.currentCharacterKey,
							'config.json'
						);
						await fsp.writeFile(configPath, JSON.stringify(char, null, 2));
						console.log(`Updated instructions for ${char.name}`);
					}
					break;
			}
		});

		ws.on('close', () => console.log('Client disconnected'));
	});
}

function broadcast(wss: WebSocketServer, message: object) {
	wss.clients.forEach((client) => {
		if (client.readyState === WebSocket.OPEN) {
			client.send(JSON.stringify(message));
		}
	});
}

// --- Core Interaction Logic (pass wss to broadcast) ---
async function handleAudioProcessing(
	wss: WebSocketServer,
	audioBase64: string,
	fileName: string
) {
	broadcast(wss, {
		type: 'STATUS_UPDATE',
		payload: { status: 'Transcribing...' },
	});
	const audioBuffer = Buffer.from(audioBase64, 'base64');

	try {
		const formData = new FormData();
		// Use the fileName from the client, with a fallback
		formData.append('audio_file', audioBuffer, fileName || 'audio.webm');
		const sttResponse = await axios.post(`${AI_API_URL}/stt`, formData, {
			headers: { ...formData.getHeaders() },
		});
		const userText = sttResponse.data.text;
		if (!userText || userText.trim().length < 2) {
			broadcast(wss, { type: 'STATUS_UPDATE', payload: { status: 'Idle' } });
			return;
		}

		state.chatHistory.push({ role: 'user', content: userText });
		broadcast(wss, {
			type: 'CHAT_MESSAGE',
			payload: { role: 'user', content: userText },
		});
		broadcast(wss, {
			type: 'STATUS_UPDATE',
			payload: { status: 'Thinking...' },
		});

		const llmResponse = await axios.post(`${AI_API_URL}/llm`, {
			prompt: userText,
			system_prompt: getSystemPrompt(),
		});
		const { text: aiText, emotion } = llmResponse.data;

		state.chatHistory.push({ role: 'assistant', content: aiText });
		broadcast(wss, {
			type: 'CHAT_MESSAGE',
			payload: { role: 'assistant', content: aiText, emotion },
		});
		broadcast(wss, {
			type: 'STATUS_UPDATE',
			payload: { status: 'Speaking...' },
		});

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
		broadcast(wss, { type: 'PLAY_AUDIO', payload: { audio: audioData } });
	} catch (error: any) {
		if (error.response) {
			console.error('Error in processing chain:', error.response.data);
		} else {
			console.error('Error in processing chain:', error.message);
		}
		broadcast(wss, { type: 'STATUS_UPDATE', payload: { status: 'Error' } });
		setTimeout(
			() =>
				broadcast(wss, { type: 'STATUS_UPDATE', payload: { status: 'Idle' } }),
			2000
		);
	}
}

// --- Server Setup ---
app.use(express.static(FRONTEND_DIR));
app.use(express.static(path.join(__dirname, '../../')));

async function startServer() {
	await loadCharacters();

	try {
		// Try to load SSL certificates
		const key = fs.readFileSync(path.join(CERTS_DIR, 'key.pem'));
		const cert = fs.readFileSync(path.join(CERTS_DIR, 'cert.pem'));
		console.log('HTTPS certificates found.');

		// 1. Create the main HTTPS server for the app
		const httpsServer = https.createServer({ key, cert }, app);
		const wss = new WebSocketServer({ server: httpsServer });
		setupWebSocketLogic(wss); // Attach WebSocket logic

		httpsServer.listen(HTTPS_PORT, () => {
			console.log(
				`✅ Secure app server running on https://localhost:${HTTPS_PORT}`
			);
			console.log(
				`   On another device, connect to https://<YOUR_COMPUTER_IP>:${HTTPS_PORT}`
			);
		});

		// 2. Create the HTTP server purely for redirection
		http
			.createServer((req, res) => {
				const host = req.headers['host'] || `localhost:${HTTP_PORT}`;
				// Redirect to the https version of the URL
				res.writeHead(301, {
					Location: `https://${host.replace(
						`:${HTTP_PORT}`,
						`:${HTTPS_PORT}`
					)}${req.url}`,
				});
				res.end();
			})
			.listen(HTTP_PORT, () => {
				console.log(
					`✅ HTTP redirector running on http://localhost:${HTTP_PORT}`
				);
			});
	} catch (error) {
		// Fallback: No certs, just run the plain HTTP server
		console.warn(
			'⚠️ Could not find SSL certificates. Starting plain HTTP server.'
		);
		console.warn(
			'   Microphone access will likely fail on mobile devices without HTTPS.'
		);

		const httpServer = http.createServer(app);
		const wss = new WebSocketServer({ server: httpServer });
		setupWebSocketLogic(wss); // Attach WebSocket logic

		httpServer.listen(HTTP_PORT, () => {
			console.log(`✅ App server listening on http://localhost:${HTTP_PORT}`);
		});
	}
}

startServer();
