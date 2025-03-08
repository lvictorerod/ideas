// Constants
const COLS = 10;
const ROWS = 20;
// Constants - Fix color definitions and block size
const BLOCK_SIZE = 30;  // Changed from 32 to 30 to fit canvas dimensions
const COLORS = [
    '#00ffff', // cyan
    '#0000ff', // blue
    '#ffa500', // orange
    '#ffff00', // yellow
    '#00ff00', // green
    '#800080', // purple
    '#ff0000'  // red
];

// Tetromino shapes defined in 4x4 grid
const SHAPES = [
    // I
    [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    // J
    [[2, 0, 0], [2, 2, 2], [0, 0, 0]],
    // L
    [[0, 0, 3], [3, 3, 3], [0, 0, 0]],
    // O
    [[4, 4], [4, 4]],
    // S
    [[0, 5, 5], [5, 5, 0], [0, 0, 0]],
    // T
    [[0, 6, 0], [6, 6, 6], [0, 0, 0]],
    // Z
    [[7, 7, 0], [0, 7, 7], [0, 0, 0]]
];

// Game variables
let canvas, ctx;
let nextPieceCanvas, nextPieceCtx;
let board;
let currentPiece, nextPiece;
let score, level, lines;
let gameOver;
let paused;
let requestId;
let dropCounter, dropInterval;
let lastTime = 0; // Add this missing variable
let showGhost = true; // Show ghost piece by default
let holdPiece = null; // For hold piece functionality
let canHold = true; // Can only hold once per piece
let highScore = localStorage.getItem('tetrisHighScore') || 0; // High score from local storage
let combo = 0; // For combo scoring

// Initialize the game
function init() {
    // Set up main canvas - Add explicit size setting
    canvas = document.getElementById('tetris');
    canvas.width = COLS * BLOCK_SIZE;
    canvas.height = ROWS * BLOCK_SIZE;
    ctx = canvas.getContext('2d');
    
    // Set up next piece canvas
    nextPieceCanvas = document.getElementById('nextPiece');
    nextPieceCanvas.width = 4 * BLOCK_SIZE;
    nextPieceCanvas.height = 4 * BLOCK_SIZE;
    nextPieceCtx = nextPieceCanvas.getContext('2d');
    
    // Set up hold piece canvas
    holdPieceCanvas = document.getElementById('holdPiece');
    holdPieceCanvas.width = 4 * BLOCK_SIZE;
    holdPieceCanvas.height = 4 * BLOCK_SIZE;
    holdPieceCtx = holdPieceCanvas.getContext('2d');
    
    // Initialize game state
    resetGame();
    
    // Set up keyboard event listeners
    document.addEventListener('keydown', handleKeyPress);
    
    // Set up touch controls for mobile devices
    setupTouchControls();
    
    // Start the game loop with proper initialization
    lastTime = 0;
    dropCounter = 0;
    requestId = requestAnimationFrame(update);
}

// Set up touch controls for mobile devices
function setupTouchControls() {
    let touchStartX = 0;
    let touchStartY = 0;
    const swipeThreshold = 30; // Minimum distance for a swipe
    
    canvas.addEventListener('touchstart', function(e) {
        if (gameOver || paused) return;
        
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        e.preventDefault();
    }, false);
    
    canvas.addEventListener('touchmove', function(e) {
        e.preventDefault(); // Prevent scrolling
    }, false);
    
    canvas.addEventListener('touchend', function(e) {
        if (gameOver || paused) return;
        
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        
        const diffX = touchEndX - touchStartX;
        const diffY = touchEndY - touchStartY;
        
        // Detect swipe direction
        if (Math.abs(diffX) > Math.abs(diffY)) {
            // Horizontal swipe
            if (Math.abs(diffX) > swipeThreshold) {
                if (diffX > 0) {
                    moveRight(); // Swipe right
                } else {
                    moveLeft(); // Swipe left
                }
            }
        } else {
            // Vertical swipe
            if (Math.abs(diffY) > swipeThreshold) {
                if (diffY > 0) {
                    moveDown(); // Swipe down (soft drop)
                } else {
                    rotatePiece(); // Swipe up (rotate)
                }
            }
        }
        
        // Detect tap (for hard drop)
        if (Math.abs(diffX) < 10 && Math.abs(diffY) < 10) {
            hardDrop();
        }
        
        e.preventDefault();
    }, false);
    
    // Add touch controls for hold piece
    holdPieceCanvas.addEventListener('touchend', function(e) {
        if (gameOver || paused) return;
        holdCurrentPiece();
        e.preventDefault();
    }, false);
}

// Reset game to initial state
function resetGame() {
    // Create empty board
    board = Array.from({length: ROWS}, () => Array(COLS).fill(0));
    
    // Reset game variables
    score = 0;
    level = 1;
    lines = 0;
    gameOver = false;
    paused = false;
    dropInterval = 1000; // Start with 1 second per drop
    holdPiece = null;
    canHold = true;
    combo = 0;
    
    // Update UI
    updateScore();
    
    // Display high score
    document.getElementById('highScore').textContent = highScore;
    
    // Create first pieces
    nextPiece = createPiece();
    getNewPiece();
    
    // Clear hold piece display
    if (holdPieceCtx) {
        holdPieceCtx.clearRect(0, 0, holdPieceCanvas.width, holdPieceCanvas.height);
    }
}

// Create a new random piece
function createPiece() {
    const pieceType = Math.floor(Math.random() * SHAPES.length);
    const piece = {
        shape: SHAPES[pieceType],
        color: COLORS[pieceType],
        x: Math.floor(COLS / 2) - Math.floor(SHAPES[pieceType][0].length / 2),
        y: 0
    };
    return piece;
}

// Get the next piece and generate a new next piece
function getNewPiece() {
    currentPiece = nextPiece;
    nextPiece = createPiece();
    drawNextPiece();
}

// Draw the next piece in the preview canvas
function drawNextPiece() {
    nextPieceCtx.clearRect(0, 0, nextPieceCanvas.width, nextPieceCanvas.height);
    
    const shape = nextPiece.shape;
    const blockSize = 20; // Smaller blocks for the preview
    
    // Center the piece in the preview canvas
    const offsetX = (nextPieceCanvas.width - shape[0].length * blockSize) / 2;
    const offsetY = (nextPieceCanvas.height - shape.length * blockSize) / 2;
    
    shape.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                nextPieceCtx.fillStyle = COLORS[value - 1];
                nextPieceCtx.fillRect(offsetX + x * blockSize, offsetY + y * blockSize, blockSize, blockSize);
                nextPieceCtx.strokeStyle = '#000';
                nextPieceCtx.strokeRect(offsetX + x * blockSize, offsetY + y * blockSize, blockSize, blockSize);
            }
        });
    });
}

// Draw a single block on the main canvas - Add explicit border and size
function drawBlock(x, y, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x * BLOCK_SIZE + 1, y * BLOCK_SIZE + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.strokeRect(x * BLOCK_SIZE + 0.5, y * BLOCK_SIZE + 0.5, BLOCK_SIZE - 1, BLOCK_SIZE - 1);
}

// Draw the current game board
function drawBoard() {
    board.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value > 0) {
                drawBlock(x, y, COLORS[value - 1]);
            }
        });
    });
}

// Draw the current falling piece
function drawPiece() {
    // Draw ghost piece first (if enabled)
    if (showGhost) {
        const ghostPiece = {
            shape: currentPiece.shape,
            x: currentPiece.x,
            y: currentPiece.y,
            color: currentPiece.color
        };
        
        // Move ghost piece down until collision
        while (!checkCollision(ghostPiece)) {
            ghostPiece.y++;
        }
        ghostPiece.y--; // Move back up one space
        
        // Draw ghost piece with transparency
        ghostPiece.shape.forEach((row, y) => {
            row.forEach((value, x) => {
                if (value !== 0) {
                    ctx.fillStyle = currentPiece.color + '40'; // Add transparency
                    ctx.fillRect((ghostPiece.x + x) * BLOCK_SIZE, (ghostPiece.y + y) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE);
                    ctx.strokeStyle = '#ffffff40';
                    ctx.strokeRect((ghostPiece.x + x) * BLOCK_SIZE, (ghostPiece.y + y) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE);
                }
            });
        });
    }
    
    // Draw actual piece
    currentPiece.shape.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                drawBlock(currentPiece.x + x, currentPiece.y + y, currentPiece.color);
            }
        });
    });
}

// Check if the current piece collides with anything
function checkCollision(piece = currentPiece) {
    for (let y = 0; y < piece.shape.length; y++) {
        for (let x = 0; x < piece.shape[y].length; x++) {
            if (piece.shape[y][x] !== 0) {
                const boardX = piece.x + x;
                const boardY = piece.y + y;
                
                // Enhanced boundary checks
                if (boardX < 0 || boardX >= COLS) return true;
                if (boardY >= ROWS) return true;
                if (boardY >= 0 && board[boardY][boardX] !== 0) return true;
            }
        }
    }
    return false;
}

// Rotate the current piece
function rotatePiece() {
    // Create a copy of the current piece to test rotation
    const originalShape = currentPiece.shape;
    const rows = originalShape.length;
    const cols = originalShape[0].length;
    
    // Create a new rotated shape matrix
    const rotatedShape = Array.from({length: cols}, () => Array(rows).fill(0));
    
    // Perform the rotation (90 degrees clockwise)
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            rotatedShape[x][rows - 1 - y] = originalShape[y][x];
        }
    }
    
    // Save the original shape
    const originalPieceShape = currentPiece.shape;
    
    // Test the rotation
    currentPiece.shape = rotatedShape;
    
    // If the rotation causes a collision, revert back
    if (checkCollision()) {
        currentPiece.shape = originalPieceShape;
    } else {
        // Play rotate sound
        if (typeof playRotateSound === 'function') {
            playRotateSound();
        }
    }
}

// Move the current piece down
function moveDown() {
    currentPiece.y++;
    
    if (checkCollision()) {
        currentPiece.y--;
        mergePiece();
        checkLines();
        getNewPiece();
        
        // Reset hold ability with each new piece
        canHold = true;
        
        // Check for game over
        if (checkCollision()) {
            gameOver = true;
            
            // Play game over sound
            if (typeof playGameOverSound === 'function') {
                playGameOverSound();
            }
        }
    }
    
    dropCounter = 0;
}

// Move the current piece left
function moveLeft() {
    currentPiece.x--;
    if (checkCollision()) {
        currentPiece.x++;
    } else {
        // Play move sound
        if (typeof playMoveSound === 'function') {
            playMoveSound();
        }
    }
}

// Move the current piece right
function moveRight() {
    currentPiece.x++;
    if (checkCollision()) {
        currentPiece.x--;
    } else {
        // Play move sound
        if (typeof playMoveSound === 'function') {
            playMoveSound();
        }
    }
}

// Hard drop - move the piece all the way down
function hardDrop() {
    while (!checkCollision()) {
        currentPiece.y++;
    }
    currentPiece.y--;
    
    // Play drop sound
    if (typeof playDropSound === 'function') {
        playDropSound();
    }
    
    moveDown(); // This will trigger the piece to lock in place
}

// Merge the current piece with the board
function mergePiece() {
    currentPiece.shape.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                const boardY = currentPiece.y + y;
                const boardX = currentPiece.x + x;
                
                // Add strict bounds checking
                if (boardY >= 0 && boardY < ROWS && 
                    boardX >= 0 && boardX < COLS) {
                    const pieceValue = COLORS.indexOf(currentPiece.color) + 1;
                    board[boardY][boardX] = pieceValue;
                }
            }
        });
    });
}

// Check for completed lines and remove them
function checkLines() {
    let linesCleared = 0;
    
    for (let y = ROWS - 1; y >= 0; y--) {
        if (board[y].every(value => value !== 0)) {
            // Remove the line
            board.splice(y, 1);
            // Add an empty line at the top
            board.unshift(Array(COLS).fill(0));
            // Since we removed a line, we need to check the same y index again
            y++;
            linesCleared++;
        }
    }
    
    if (linesCleared > 0) {
        // Play clear sound
        if (typeof playClearSound === 'function') {
            playClearSound();
        }
        
        // Play level up sound if level increases
        const oldLevel = level;
        
        // Update score based on lines cleared
        updateScore(linesCleared);
        
        if (level > oldLevel && typeof playLevelUpSound === 'function') {
            playLevelUpSound();
        }
    }
}

// Update the score, level, and lines
function updateScore(linesCleared = 0) {
    if (linesCleared > 0) {
        // Classic Tetris scoring system
        const linePoints = [40, 100, 300, 1200]; // Points for 1, 2, 3, 4 lines
        
        // Add combo bonus
        if (linesCleared > 0) {
            combo++;
        } else {
            combo = 0;
        }
        
        // Calculate score with combo bonus
        let comboBonus = combo > 1 ? combo * 50 : 0;
        score += (linePoints[linesCleared - 1] * level) + comboBonus;
        
        // Update high score if needed
        if (score > highScore) {
            highScore = score;
            localStorage.setItem('tetrisHighScore', highScore);
        }
        
        // Update lines count
        lines += linesCleared;
        
        // Update level (every 10 lines)
        const newLevel = Math.floor(lines / 10) + 1;
        if (newLevel > level) {
            level = newLevel;
            // Increase speed with level
            dropInterval = Math.max(100, 1000 - (level - 1) * 100);
        }
    }
    
    // Update UI
    document.getElementById('score').textContent = score;
    document.getElementById('level').textContent = level;
    document.getElementById('lines').textContent = lines;
}

// Draw the hold piece in the hold piece canvas
function drawHoldPiece() {
    if (!holdPiece) return;
    
    holdPieceCtx.clearRect(0, 0, holdPieceCanvas.width, holdPieceCanvas.height);
    
    const shape = holdPiece.shape;
    const blockSize = 20; // Smaller blocks for the preview
    
    // Center the piece in the hold piece canvas
    const offsetX = (holdPieceCanvas.width - shape[0].length * blockSize) / 2;
    const offsetY = (holdPieceCanvas.height - shape.length * blockSize) / 2;
    
    shape.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                holdPieceCtx.fillStyle = holdPiece.color;
                holdPieceCtx.fillRect(offsetX + x * blockSize, offsetY + y * blockSize, blockSize, blockSize);
                holdPieceCtx.strokeStyle = '#000';
                holdPieceCtx.strokeRect(offsetX + x * blockSize, offsetY + y * blockSize, blockSize, blockSize);
            }
        });
    });
}

// Hold the current piece
function holdCurrentPiece() {
    if (!canHold) return;
    
    // Play hold sound
    if (typeof playHoldSound === 'function') {
        playHoldSound();
    }
    
    if (holdPiece === null) {
        // First hold - store current piece and get a new one
        holdPiece = {
            shape: currentPiece.shape,
            color: currentPiece.color
        };
        getNewPiece();
    } else {
        // Swap current piece with hold piece
        const temp = {
            shape: currentPiece.shape,
            color: currentPiece.color
        };
        
        currentPiece = {
            shape: holdPiece.shape,
            color: holdPiece.color,
            x: Math.floor(COLS / 2) - Math.floor(holdPiece.shape[0].length / 2),
            y: 0
        };
        
        holdPiece = temp;
    }
    
    canHold = false; // Can't hold again until a new piece is placed
    drawHoldPiece();
}

// Handle keyboard input
function handleKeyPress(event) {
    if (gameOver) {
        if (event.key === 'Enter') {
            cancelAnimationFrame(requestId); // Stop existing loop
            resetGame();
            requestId = requestAnimationFrame(update);
            return;
        }
        return;
    }
    
    if (event.key === 'p' || event.key === 'P') {
        togglePause();
        return;
    }
    
    if (paused) return;
    
    switch (event.key) {
        case 'ArrowLeft':
            moveLeft();
            break;
        case 'ArrowRight':
            moveRight();
            break;
        case 'ArrowDown':
            moveDown();
            break;
        case 'ArrowUp':
            rotatePiece();
            break;
        case ' ':
            hardDrop();
            break;
        case 'c':
        case 'C':
            holdCurrentPiece();
            break;
    }
}

// Toggle pause state
function togglePause() {
    paused = !paused;
    if (!paused) {
        // Resume the game
        requestId = requestAnimationFrame(update);
    } else {
        // Pause the game
        cancelAnimationFrame(requestId);
        
        // Draw pause message
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '30px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('PAUSED', canvas.width / 2, canvas.height / 2);
        ctx.font = '16px Arial';
        ctx.fillText('Press P to resume', canvas.width / 2, canvas.height / 2 + 40);
    }
}

// Main game loop
function update(time = 0) {
    if (gameOver) {
        // Draw game over message
        ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = '30px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 - 30);
        ctx.font = '20px Arial';
        ctx.fillText(`Score: ${score}`, canvas.width / 2, canvas.height / 2 + 10);
        
        // Show high score on game over screen
        if (score >= highScore) {
            ctx.fillText(`New High Score!`, canvas.width / 2, canvas.height / 2 + 30);
        } else {
            ctx.fillText(`High Score: ${highScore}`, canvas.width / 2, canvas.height / 2 + 30);
        }
        
        ctx.font = '16px Arial';
        ctx.fillText('Press ENTER to restart', canvas.width / 2, canvas.height / 2 + 60);
        return;
    }
    
    if (paused) return;
    
    // Fix deltaTime calculation
    const deltaTime = time - lastTime;
    lastTime = time;
    dropCounter += deltaTime;

    // Move piece down when timer exceeds drop interval
    if (dropCounter > dropInterval) {
        moveDown();
        dropCounter = 0;
    }
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw game elements
    drawBoard();
    drawPiece();
    
    // Continue the game loop
    requestId = requestAnimationFrame(update);
}

// Start the game when the page loads
document.addEventListener('DOMContentLoaded', init);