document.addEventListener('DOMContentLoaded', () => {
    // Elementos del DOM
    const menuScreen = document.getElementById('menu-screen');
    const gameScreen = document.getElementById('game-screen');
    const playerNameInput = document.getElementById('player-name');
    const roomIdInput = document.getElementById('room-id');
    const playButton = document.getElementById('play-button');
    const backButton = document.getElementById('back-button');
    const roomDisplay = document.getElementById('room-display');
    const scoreboard = document.getElementById('scoreboard');
    const canvas = document.getElementById('game-canvas');
    const ctx = canvas.getContext('2d');
  
    // Variables del juego
    let socket;
    let gameState = null;
    let playerName = '';
    let roomId = '';
    let cellSize = 20;
    const gridSize = 20;
    let gridOffscreen; // offscreen canvas para la cuadrícula
  
    // Mapeo para teclas direccionales
    const keyMap = {
      'ArrowUp': 'up', 'w': 'up', 'W': 'up',
      'ArrowDown': 'down', 's': 'down', 'S': 'down',
      'ArrowLeft': 'left', 'a': 'left', 'A': 'left',
      'ArrowRight': 'right', 'd': 'right', 'D': 'right'
    };
  
    // Ajusta el tamaño del canvas y actualiza la variable cellSize
    function resizeCanvas() {
      const size = Math.min(window.innerWidth - 40, window.innerHeight - 200, 600);
      canvas.width = size;
      canvas.height = size;
      cellSize = size / gridSize;
      // Redibuja la cuadrícula en el offscreen
      gridOffscreen = document.createElement('canvas');
      gridOffscreen.width = canvas.width;
      gridOffscreen.height = canvas.height;
      const offCtx = gridOffscreen.getContext('2d');
      drawGrid(offCtx);
    }
  
    // Dibuja la cuadrícula en un canvas dado
    function drawGrid(context) {
      context.strokeStyle = '#333';
      context.lineWidth = 0.5;
      for (let i = 0; i <= gridSize; i++) {
        // Líneas verticales
        context.beginPath();
        context.moveTo(i * cellSize, 0);
        context.lineTo(i * cellSize, canvas.height);
        context.stroke();
        // Líneas horizontales
        context.beginPath();
        context.moveTo(0, i * cellSize);
        context.lineTo(canvas.width, i * cellSize);
        context.stroke();
      }
    }
  
    // Inicializa el juego y asigna los event listeners
    function init() {
      playButton.addEventListener('click', joinGame);
      backButton.addEventListener('click', leaveGame);
      window.addEventListener('resize', resizeCanvas);
      window.addEventListener('keydown', handleKeyPress);
      roomIdInput.value = roomIdInput.value || generateRoomId();
      if (!playerNameInput.value) {
        playerNameInput.value = 'Jugador' + Math.floor(Math.random() * 1000);
      }
      resizeCanvas();
      setupTouchControls();
    }
  
    // Configura controles táctiles
    function setupTouchControls() {
      const touchControls = document.createElement('div');
      touchControls.id = 'touch-controls';
      touchControls.innerHTML = `
        <div class="touch-row">
            <button id="up-btn">↑</button>
        </div>
        <div class="touch-row">
            <button id="left-btn">←</button>
            <button id="down-btn">↓</button>
            <button id="right-btn">→</button>
        </div>`;
      gameScreen.appendChild(touchControls);
      document.getElementById('up-btn').addEventListener('touchstart', () => handleDirectionChange('up'));
      document.getElementById('down-btn').addEventListener('touchstart', () => handleDirectionChange('down'));
      document.getElementById('left-btn').addEventListener('touchstart', () => handleDirectionChange('left'));
      document.getElementById('right-btn').addEventListener('touchstart', () => handleDirectionChange('right'));
    }
  
    // Cambia la dirección enviando el mensaje al servidor
    function handleDirectionChange(direction) {
      if (socket && gameState) {
        socket.emit('changeDirection', direction);
      }
    }
  
    // Genera un ID de sala aleatorio
    function generateRoomId() {
      return Math.random().toString(36).substring(2, 8).toUpperCase();
    }
  
    // Une al jugador a la sala y establece la conexión WebSocket
    function joinGame() {
      playerName = playerNameInput.value.trim();
      roomId = roomIdInput.value.trim();
      if (!playerName || !roomId) {
        alert('Ingresa tu nombre y un ID de sala');
        return;
      }
      socket = io();
      setupSocketEvents();
      socket.emit('joinRoom', { roomId, playerName });
      menuScreen.style.display = 'none';
      gameScreen.style.display = 'block';
      roomDisplay.textContent = roomId;
      requestAnimationFrame(gameLoop);
    }
  
    // Sale del juego y restablece el estado
    function leaveGame() {
      if (socket) {
        socket.disconnect();
      }
      gameState = null;
      menuScreen.style.display = 'block';
      gameScreen.style.display = 'none';
    }
  
    // Configura los eventos del socket
    function setupSocketEvents() {
      socket.on('gameState', (state) => {
        gameState = state;
        updateScoreboard();
      });
      socket.on('gameOver', () => {
        alert('¡Juego terminado! Todos los jugadores han muerto.');
        leaveGame();
      });
      socket.on('playerJoined', (player) => {
        console.log(`${player.name} se unió al juego`);
      });
      socket.on('playerLeft', (playerId) => {
        console.log('Un jugador salió del juego');
      });
      socket.on('powerUpCollected', (data) => {
        const name = gameState.players[data.playerId]?.name || 'Un jugador';
        const powerUpName = getPowerUpName(data.type);
        showNotification(`${name} recogió ${powerUpName}!`);
      });
      socket.on('disconnect', () => {
        console.log('Desconectado del servidor');
        alert('Se perdió la conexión con el servidor');
        leaveGame();
      });
    }
  
    // Maneja la pulsación de teclas usando el objeto keyMap
    function handleKeyPress(e) {
      if (!socket || !gameState) return;
      const direction = keyMap[e.key];
      if (direction) {
        socket.emit('changeDirection', direction);
      }
    }
  
    // Actualiza el marcador de puntajes
    function updateScoreboard() {
      if (!gameState) return;
      scoreboard.innerHTML = '';
      for (const playerId in gameState.players) {
        const player = gameState.players[playerId];
        const scoreElement = document.createElement('div');
        scoreElement.className = 'player-score';
        scoreElement.style.backgroundColor = player.color;
        scoreElement.textContent = `${player.name}: ${player.score}`;
        if (!player.alive) {
          scoreElement.style.opacity = '0.5';
          scoreElement.textContent += ' (Muerto)';
        }
        scoreboard.appendChild(scoreElement);
      }
    }
  
    // Bucle principal de renderizado
    function gameLoop() {
      if (gameState) {
        drawGame();
      }
      requestAnimationFrame(gameLoop);
    }
  
    // Dibuja el estado del juego sobre el canvas
    function drawGame() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      // Dibuja la cuadrícula desde el offscreen canvas
      if (gridOffscreen) ctx.drawImage(gridOffscreen, 0, 0);
      drawObstacles();
      drawPowerUp();
      drawFood();
      drawSnakes();
    }
  
    // Dibuja la comida
    function drawFood() {
      if (!gameState || !gameState.food) return;
      const food = gameState.food;
      ctx.fillStyle = '#FF0000';
      ctx.beginPath();
      ctx.arc(
        (food.x + 0.5) * cellSize,
        (food.y + 0.5) * cellSize,
        cellSize / 2.5,
        0,
        Math.PI * 2
      );
      ctx.fill();
    }
  
    // Dibuja todos los jugadores (serpientes)
    function drawSnakes() {
      if (!gameState || !gameState.players) return;
      for (const playerId in gameState.players) {
        const player = gameState.players[playerId];
        if (!player.snake || player.snake.length === 0) continue;
        ctx.fillStyle = player.color;
        ctx.globalAlpha = player.alive ? 1 : 0.5;
        const hasSpeedBoost = player.speedMultiplier > 1;
        const isInvincible = player.invincible;
        player.snake.forEach((segment, i) => {
          ctx.save();
          if (isInvincible) {
            ctx.shadowColor = '#00FF00';
            ctx.shadowBlur = 10;
          }
          ctx.fillRect(
            segment.x * cellSize + 1,
            segment.y * cellSize + 1,
            cellSize - 2,
            cellSize - 2
          );
          ctx.restore();
          if (i === 0 && player.alive) {
            drawSnakeEyes(segment, player.direction);
            if (hasSpeedBoost) drawSpeedLines(segment, player.direction);
          }
        });
      }
      ctx.globalAlpha = 1;
    }
  
    // Dibuja los "ojos" de la cabeza de la serpiente
    function drawSnakeEyes(head, direction) {
      ctx.fillStyle = '#FFFFFF';
      const eyeSize = cellSize / 6;
      const eyeOffset = cellSize / 4;
      const x = head.x * cellSize;
      const y = head.y * cellSize;
      switch (direction) {
        case 'up':
          ctx.fillRect(x + eyeOffset, y + eyeOffset, eyeSize, eyeSize);
          ctx.fillRect(x + cellSize - eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
          break;
        case 'down':
          ctx.fillRect(x + eyeOffset, y + cellSize - eyeOffset - eyeSize, eyeSize, eyeSize);
          ctx.fillRect(x + cellSize - eyeOffset - eyeSize, y + cellSize - eyeOffset - eyeSize, eyeSize, eyeSize);
          break;
        case 'left':
          ctx.fillRect(x + eyeOffset, y + eyeOffset, eyeSize, eyeSize);
          ctx.fillRect(x + eyeOffset, y + cellSize - eyeOffset - eyeSize, eyeSize, eyeSize);
          break;
        case 'right':
          ctx.fillRect(x + cellSize - eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
          ctx.fillRect(x + cellSize - eyeOffset - eyeSize, y + cellSize - eyeOffset - eyeSize, eyeSize, eyeSize);
          break;
      }
    }
  
    // Dibuja líneas de velocidad para efectos de "speed boost"
    function drawSpeedLines(segment, direction) {
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2;
      ctx.beginPath();
      const startX = segment.x * cellSize + cellSize / 2;
      const startY = segment.y * cellSize + cellSize / 2;
      let endX = startX, endY = startY;
      const offset = cellSize;
      switch (direction) {
        case 'up': endY -= offset; break;
        case 'down': endY += offset; break;
        case 'left': endX -= offset; break;
        case 'right': endX += offset; break;
      }
      ctx.moveTo(startX, startY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
    }
  
    // Dibuja obstáculos (obtenidos del estado del juego)
    function drawObstacles() {
      if (!gameState || !gameState.obstacles) return;
      ctx.fillStyle = '#555555';
      for (const obstacle of gameState.obstacles) {
        ctx.fillRect(
          obstacle.x * cellSize,
          obstacle.y * cellSize,
          cellSize,
          cellSize
        );
      }
    }
  
    // Dibuja power-ups con efecto de estrella
    function drawPowerUp() {
      if (!gameState || !gameState.powerUp) return;
      const powerUp = gameState.powerUp;
      let color;
      switch (powerUp.type) {
        case 'speed': color = '#FFFF00'; break;
        case 'slow': color = '#0000FF'; break;
        case 'invincible': color = '#00FF00'; break;
        case 'doublePoints': color = '#FF00FF'; break;
        default: color = '#FFFFFF';
      }
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(
        (powerUp.x + 0.5) * cellSize,
        (powerUp.y + 0.5) * cellSize,
        cellSize / 2,
        0,
        Math.PI * 2
      );
      ctx.fill();
      // Dibuja la estrella
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < 5; i++) {
        const angle = (i * 2 * Math.PI / 5) - Math.PI / 2;
        const x = (powerUp.x + 0.5) * cellSize + Math.cos(angle) * (cellSize / 3);
        const y = (powerUp.y + 0.5) * cellSize + Math.sin(angle) * (cellSize / 3);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
    }
  
    // Devuelve el nombre amigable para el tipo de power-up
    function getPowerUpName(type) {
      switch (type) {
        case 'speed': return 'Aumento de Velocidad';
        case 'slow': return 'Ralentizar';
        case 'invincible': return 'Invencible';
        case 'doublePoints': return 'Puntos Dobles';
        default: return 'Power-Up';
      }
    }
  
    // Muestra una notificación temporal en pantalla
    function showNotification(message) {
      const notification = document.createElement('div');
      notification.className = 'game-notification';
      notification.textContent = message;
      gameScreen.appendChild(notification);
      setTimeout(() => { notification.style.opacity = '1'; }, 10);
      setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => { gameScreen.removeChild(notification); }, 500);
      }, 3000);
    }
  
    init();
  });
  