// Sound effects for Tetris game

// Sound variables
let audioContext;
let soundEnabled = true;
let sounds = {};

// Initialize audio
function initAudio() {
    try {
        // Create audio context
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContext();
        
        // Create sounds
        createSounds();
        
        // Add sound toggle button
        createSoundToggle();
    } catch (e) {
        console.warn('Web Audio API not supported in this browser');
        soundEnabled = false;
    }
}

// Create sound toggle button
function createSoundToggle() {
    const controlsDiv = document.querySelector('.controls');
    
    const soundToggle = document.createElement('div');
    soundToggle.className = 'sound-toggle';
    soundToggle.innerHTML = `
        <button id="toggleSound">${soundEnabled ? 'Sound: ON' : 'Sound: OFF'}</button>
    `;
    
    controlsDiv.appendChild(soundToggle);
    
    // Add event listener
    document.getElementById('toggleSound').addEventListener('click', function() {
        soundEnabled = !soundEnabled;
        this.textContent = soundEnabled ? 'Sound: ON' : 'Sound: OFF';
    });
}

// Create all game sounds
function createSounds() {
    // Define sound specifications
    const soundSpecs = {
        move: { type: 'noise', duration: 0.05, frequency: 300 },
        rotate: { type: 'oscillator', duration: 0.08, frequency: 440 },
        drop: { type: 'oscillator', duration: 0.15, frequency: 200 },
        clear: { type: 'oscillator', duration: 0.3, frequency: 600 },
        levelUp: { type: 'arpeggio', duration: 0.5, notes: [440, 554, 659, 880] },
        gameOver: { type: 'arpeggio', duration: 1.5, notes: [330, 262, 196, 165] },
        hold: { type: 'oscillator', duration: 0.1, frequency: 330 }
    };
    
    // Create each sound
    for (const [name, spec] of Object.entries(soundSpecs)) {
        sounds[name] = createSound(spec);
    }
}

// Create a single sound based on specifications
function createSound(spec) {
    switch (spec.type) {
        case 'oscillator':
            return () => playTone(spec.frequency, spec.duration);
        case 'noise':
            return () => playNoise(spec.duration, spec.frequency);
        case 'arpeggio':
            return () => playArpeggio(spec.notes, spec.duration);
        default:
            return () => {};
    }
}

// Play a simple tone
function playTone(frequency, duration) {
    if (!soundEnabled || !audioContext) return;
    
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.type = 'sine';
    oscillator.frequency.value = frequency;
    
    // Connect nodes
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    // Start sound
    const now = audioContext.currentTime;
    oscillator.start(now);
    
    // Fade out
    gainNode.gain.setValueAtTime(0.5, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + duration);
    
    // Stop sound
    oscillator.stop(now + duration);
}

// Play noise sound
function playNoise(duration, frequency) {
    if (!soundEnabled || !audioContext) return;
    
    const bufferSize = audioContext.sampleRate * duration;
    const buffer = audioContext.createBuffer(1, bufferSize, audioContext.sampleRate);
    const data = buffer.getChannelData(0);
    
    // Fill buffer with noise
    for (let i = 0; i < bufferSize; i++) {
        data[i] = Math.random() * 2 - 1;
    }
    
    // Create source node
    const noise = audioContext.createBufferSource();
    noise.buffer = buffer;
    
    // Create filter to shape noise
    const filter = audioContext.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = frequency;
    filter.Q.value = 1;
    
    // Create gain node for volume control
    const gainNode = audioContext.createGain();
    
    // Connect nodes
    noise.connect(filter);
    filter.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    // Start sound
    const now = audioContext.currentTime;
    noise.start(now);
    
    // Fade out
    gainNode.gain.setValueAtTime(0.3, now);
    gainNode.gain.exponentialRampToValueAtTime(0.001, now + duration);
    
    // Stop sound
    noise.stop(now + duration);
}

// Play arpeggio (sequence of notes)
function playArpeggio(notes, totalDuration) {
    if (!soundEnabled || !audioContext) return;
    
    const noteDuration = totalDuration / notes.length;
    
    notes.forEach((frequency, index) => {
        const startTime = audioContext.currentTime + (index * noteDuration);
        
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        
        // Connect nodes
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Start sound
        oscillator.start(startTime);
        
        // Fade out
        gainNode.gain.setValueAtTime(0.5, startTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + noteDuration);
        
        // Stop sound
        oscillator.stop(startTime + noteDuration);
    });
}

// Sound playback functions
function playMoveSound() {
    sounds.move && sounds.move();
}

function playRotateSound() {
    sounds.rotate && sounds.rotate();
}

function playDropSound() {
    sounds.drop && sounds.drop();
}

function playClearSound() {
    sounds.clear && sounds.clear();
}

function playLevelUpSound() {
    sounds.levelUp && sounds.levelUp();
}

function playGameOverSound() {
    sounds.gameOver && sounds.gameOver();
}

function playHoldSound() {
    sounds.hold && sounds.hold();
}

// Initialize audio when the page loads
document.addEventListener('DOMContentLoaded', initAudio);