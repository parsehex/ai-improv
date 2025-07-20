import { parse } from 'partial-json';

// --- DOM Elements ---
const containerEl = document.querySelector('.container') as HTMLDivElement;
const statusEl = document.getElementById('status')!;
const pttButton = document.getElementById('ptt-button') as HTMLButtonElement;
const characterSelect = document.getElementById(
	'character-select'
) as HTMLSelectElement;
const chatHistoryEl = document.getElementById('chat-history')!;
const characterImage = document.getElementById(
	'character-image'
) as HTMLImageElement;
const toggleRecordCheck = document.getElementById(
	'toggle-record'
) as HTMLInputElement;
const systemPromptText = document.getElementById(
	'system-prompt'
) as HTMLTextAreaElement;
const savePromptButton = document.getElementById(
	'save-prompt-button'
) as HTMLButtonElement;

// --- State ---
let ws: WebSocket;
let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
let characters: Record<string, any> = {};
let currentCharacterKey: string | null = null;
let isToggleRecording = false;
const TOGGLE_RECORD_KEY = 'aiImprov-toggleRecord';

// State for streaming response
let currentAssistantMessageEl: HTMLDivElement | null = null;
let currentResponseText = '';
let lastResponseEmotion: string | null = null;
let processedTextForTTS = '';

// State for sentence-by-sentence audio playback
let audioQueue: string[] = [];
let isPlayingAudio = false;
let audioStreamHasEnded = false;

// --- WebSocket Connection ---
function connect() {
	const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
	ws = new WebSocket(`${protocol}://${window.location.host}`);

	ws.onopen = () => updateStatus('Idle');
	ws.onclose = () => updateStatus('Disconnected');
	ws.onerror = () => updateStatus('Error');
	ws.onmessage = (event) => {
		const { type, payload } = JSON.parse(event.data);
		handleMessage(type, payload);
	};
}

// --- Message Handling ---
function handleMessage(type: string, payload: any) {
	switch (type) {
		case 'INIT_STATE':
			characters = payload.characters;
			populateCharacterSelector(payload.currentCharacterKey);
			payload.chatHistory.forEach((msg: any) =>
				addChatMessage(msg.role, msg.content)
			);
			break;
		case 'STATUS_UPDATE':
			if (!isPlayingAudio) {
				updateStatus(payload.status);
			}
			break;
		case 'CHAT_MESSAGE':
			addChatMessage(payload.role, payload.content);
			break;
		case 'AI_RESPONSE_START':
			const msgDiv = document.createElement('div');
			msgDiv.classList.add('chat-message', 'assistant-message');
			chatHistoryEl.appendChild(msgDiv);
			chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
			currentAssistantMessageEl = msgDiv;
			currentResponseText = '';
			lastResponseEmotion = null;
			processedTextForTTS = ''; // Reset TTS tracker
			audioQueue = [];
			isPlayingAudio = false;
			audioStreamHasEnded = false;
			updateCharacterImage('talking');
			break;
		case 'AI_RESPONSE_CHUNK':
			if (!currentAssistantMessageEl) return;
			currentResponseText += payload.chunk;
			try {
				const partialData = parse(currentResponseText);
				if (partialData.text) {
					currentAssistantMessageEl.textContent = partialData.text;
					// Process the newly received text for sentences
					processNewTextForTTS(partialData.text);
				}
			} catch (e) {
				currentAssistantMessageEl.textContent = currentResponseText;
			}
			chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
			break;
		case 'AI_RESPONSE_END':
			if (currentAssistantMessageEl) {
				try {
					const finalData = JSON.parse(currentResponseText);
					if (finalData.emotion) {
						lastResponseEmotion = finalData.emotion;
					}
					// Process any remaining text after the stream ends
					processNewTextForTTS(finalData.text, true);
				} catch (e) {
					console.error("Couldn't parse final JSON for emotion", e);
				}
			}
			currentAssistantMessageEl = null;
			break;
		case 'PLAY_AUDIO':
			audioQueue.push(payload.audio);
			playNextInQueue();
			break;
		case 'AUDIO_STREAM_END':
			audioStreamHasEnded = true;
			playNextInQueue();
			break;
		case 'CHARACTER_SWITCHED':
			populateCharacterSelector(payload.key, true);
			systemPromptText.value = payload.instructions || '';
			break;
		case 'CHAT_CLEAR':
			chatHistoryEl.innerHTML = '';
			break;
	}
}

function sendMessage(type: string, payload: object) {
	if (ws.readyState === WebSocket.OPEN) {
		ws.send(JSON.stringify({ type, payload }));
	}
}

function processNewTextForTTS(fullText: string, isFinal = false) {
	// Find the portion of the text that we haven't processed yet
	let newText = fullText.substring(processedTextForTTS.length);

	const sentenceEndRegex = /([^.!?]+[.!?])\s*/g;
	let match;

	while ((match = sentenceEndRegex.exec(newText)) !== null) {
		const sentence = match[1].trim();
		if (sentence) {
			console.log(`Client detected sentence: "${sentence}"`);
			sendMessage('REQUEST_TTS_FOR_SENTENCE', { sentence });
			// Update the tracker to include the sentence we just processed
			processedTextForTTS += match[0];
		}
	}

	// If this is the final chunk, send any remaining text as a sentence
	if (isFinal) {
		newText = fullText.substring(processedTextForTTS.length);
		const remainingSentence = newText.trim();
		if (remainingSentence) {
			console.log(`Client detected final sentence: "${remainingSentence}"`);
			sendMessage('REQUEST_TTS_FOR_SENTENCE', { sentence: remainingSentence });
			processedTextForTTS = fullText;
		}
	}
}

// --- UI Updates ---
function updateStatus(status: string) {
	statusEl.textContent = status;
	pttButton.disabled = !['Idle', 'Listening...'].includes(status);
	pttButton.classList.remove('listening', 'processing');
	if (status === 'Listening...') pttButton.classList.add('listening');
	if (!['Idle', 'Listening...'].includes(status))
		pttButton.classList.add('processing');
}

function addChatMessage(role: 'user' | 'assistant', content: string) {
	const msgDiv = document.createElement('div');
	msgDiv.classList.add('chat-message', `${role}-message`);
	msgDiv.textContent = content;
	chatHistoryEl.appendChild(msgDiv);
	chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

function populateCharacterSelector(selectedKey: string, isUpdate = false) {
	currentCharacterKey = selectedKey;
	if (!isUpdate) {
		characterSelect.innerHTML = '';
		for (const key in characters) {
			const option = document.createElement('option');
			option.value = key;
			option.textContent = characters[key].name;
			characterSelect.appendChild(option);
		}
	}
	characterSelect.value = selectedKey;
	systemPromptText.value = characters[selectedKey]?.instructions || '';
	updateCharacterImage('neutral');
}

function updateCharacterImage(emotion: string) {
	if (!currentCharacterKey) return;
	const imagePath = characters[currentCharacterKey].images[emotion];
	characterImage.src = `${imagePath}`;
}

// --- Audio Handling ---
async function startRecording() {
	if (mediaRecorder?.state === 'recording') return;
	updateStatus('Listening...');

	try {
		const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		mediaRecorder = new MediaRecorder(stream);
		audioChunks = [];
		mediaRecorder.ondataavailable = (event) => audioChunks.push(event.data);

		mediaRecorder.onstop = () => {
			if (audioChunks.length === 0 || !mediaRecorder) {
				console.warn('No audio data recorded.');
				updateStatus('Idle');
				return;
			}
			const mimeType = mediaRecorder.mimeType;
			const audioBlob = new Blob(audioChunks, { type: mimeType });
			const extension = mimeType.split(';')[0].split('/')[1];
			const fileName = `audio.${extension}`;
			console.log(`Recorded audio as ${fileName} (MIME: ${mimeType})`);

			const reader = new FileReader();
			reader.onloadend = () => {
				const base64 = (reader.result as string).split(',')[1];
				sendMessage('PROCESS_AUDIO', { audio: base64, fileName: fileName });
			};
			reader.readAsDataURL(audioBlob);
		};
		mediaRecorder.start();
	} catch (err) {
		console.error('Error getting audio stream:', err);
		updateStatus('Mic Error!');
		alert(
			'Could not access the microphone. On mobile, this often requires an HTTPS connection.'
		);
	}
}

function stopRecording() {
	if (mediaRecorder?.state === 'recording') {
		mediaRecorder.stop();
	}
}

function playNextInQueue() {
	if (isPlayingAudio || audioQueue.length === 0) {
		if (!isPlayingAudio && audioStreamHasEnded && audioQueue.length === 0) {
			handleAllAudioFinished();
		}
		return;
	}

	isPlayingAudio = true;
	updateStatus('Speaking...');

	const audioBase64 = audioQueue.shift()!;
	const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
	audio.play().catch((e) => {
		console.error('Audio playback failed:', e);
		isPlayingAudio = false;
		playNextInQueue();
	});

	audio.onended = () => {
		isPlayingAudio = false;
		playNextInQueue();
	};
}

function handleAllAudioFinished() {
	console.log('All queued audio has finished playing.');
	updateStatus('Idle');
	if (lastResponseEmotion) {
		updateCharacterImage(lastResponseEmotion);
	} else {
		updateCharacterImage('neutral');
	}
	audioStreamHasEnded = false;
}

// --- Event Listeners ---
pttButton.addEventListener('mousedown', () => {
	if (!toggleRecordCheck.checked) startRecording();
});
pttButton.addEventListener('mouseup', () => {
	if (!toggleRecordCheck.checked) stopRecording();
});
pttButton.addEventListener('click', () => {
	if (toggleRecordCheck.checked) {
		if (isToggleRecording) {
			stopRecording();
			isToggleRecording = false;
		} else {
			startRecording();
			isToggleRecording = true;
		}
	}
});

characterSelect.addEventListener('change', () => {
	sendMessage('SWITCH_CHARACTER', { key: characterSelect.value });
});

savePromptButton.addEventListener('click', () => {
	sendMessage('SET_INSTRUCTIONS', { instructions: systemPromptText.value });
	alert('Instructions saved!');
});

characterImage.addEventListener('click', () => {
	containerEl.classList.toggle('focus-mode');
});

toggleRecordCheck.addEventListener('change', () => {
	localStorage.setItem(TOGGLE_RECORD_KEY, String(toggleRecordCheck.checked));
});

// --- Initialization ---
const savedToggleState = localStorage.getItem(TOGGLE_RECORD_KEY);
toggleRecordCheck.checked = savedToggleState === 'true';

connect();
