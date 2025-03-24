const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

// Servir archivos estáticos desde el directorio 'public'
app.use(express.static(path.join(__dirname, 'public')));

// Estado global de juegos
const games = {};

// Configuración del juego
const GRID_SIZE = 20;
const GAME_SPEED = 200; // en milisegundos

// Tipos de power-up y configuraciones
const POWER_UP_TYPES = {
  SPEED: 'speed',
  SLOW: 'slow',
  INVINCIBLE: 'invincible',
  DOUBLE_POINTS: 'doublePoints'
};
const POWER_UP_DURATION = 5000; // 5 segundos
const POWER_UP_SPAWN_CHANCE = 0.1; // 10%

// Crea un juego nuevo en una sala
function createGame(roomId, gameMode = 'classic') {
  games[roomId] = {
    players: {},
    food: null,
    obstacles: [],
    gameInterval: null,
    active: false,
    mode: gameMode,
    speedMultiplier: gameMode === 'fast' ? 1.5 : 1,
    growthFactor: gameMode === 'growth' ? 2 : 1,
    powerUp: null
  };
  games[roomId].food = generateFood(games[roomId].players);
  if (gameMode === 'walls') {
    generateWalls(roomId);
  }
}

// Genera posición aleatoria para la comida asegurándose que no se superponga con alguna serpiente
function generateFood(players) {
  let position, valid = false;
  while (!valid) {
    position = {
      x: Math.floor(Math.random() * GRID_SIZE),
      y: Math.floor(Math.random() * GRID_SIZE)
    };
    valid = true;
    for (const playerId in players) {
      const snake = players[playerId].snake;
      for (const segment of snake) {
        if (segment.x === position.x && segment.y === position.y) {
          valid = false;
          break;
        }
      }
      if (!valid) break;
    }
  }
  return position;
}

// Genera paredes (obstáculos) para el modo WALLS
function generateWalls(roomId) {
  const NUM_WALLS = 5;
  const WALL_LENGTH = 4;
  for (let i = 0; i < NUM_WALLS; i++) {
    const horizontal = Math.random() > 0.5;
    const startX = Math.floor(Math.random() * (GRID_SIZE - WALL_LENGTH));
    const startY = Math.floor(Math.random() * (GRID_SIZE - WALL_LENGTH));
    for (let j = 0; j < WALL_LENGTH; j++) {
      const obstacle = {
        x: horizontal ? startX + j : startX,
        y: horizontal ? startY : startY + j
      };
      games[roomId].obstacles.push(obstacle);
    }
  }
}

// Crea un jugador nuevo en la sala
function createPlayer(roomId, playerId, playerName) {
  const startX = Math.floor(Math.random() * (GRID_SIZE - 5)) + 2;
  const startY = Math.floor(Math.random() * (GRID_SIZE - 5)) + 2;
  const colors = ['#FF5733', '#33FF57', '#3357FF', '#F3FF33', '#FF33F3', '#33FFF3'];
  const color = colors[Math.floor(Math.random() * colors.length)];
  games[roomId].players[playerId] = {
    name: playerName,
    snake: [{ x: startX, y: startY }],
    direction: 'right',
    color: color,
    score: 0,
    alive: true,
    speedMultiplier: 1,
    invincible: false,
    pointsMultiplier: 1
  };
}

// Actualiza el estado del juego en cada tick
function updateGame(roomId) {
  const game = games[roomId];
  if (!game) return;
  const players = game.players;
  const food = game.food;

  for (const playerId in players) {
    const player = players[playerId];
    if (!player.alive) continue;
    const snake = player.snake;
    let head = { ...snake[0] };

    // Actualiza la cabeza según la dirección
    switch (player.direction) {
      case 'up': head.y -= 1; break;
      case 'down': head.y += 1; break;
      case 'left': head.x -= 1; break;
      case 'right': head.x += 1; break;
    }

    // Verifica colisión con paredes del mapa
    if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
      player.alive = false;
      continue;
    }

    // Colisión con obstáculos (salir tan pronto se detecte)
    for (const obstacle of game.obstacles) {
      if (head.x === obstacle.x && head.y === obstacle.y) {
        player.alive = false;
        break;
      }
    }
    if (!player.alive) continue;

    // Colisión con la propia serpiente
    for (let i = 0; i < snake.length; i++) {
      if (snake[i].x === head.x && snake[i].y === head.y) {
        player.alive = false;
        break;
      }
    }
    if (!player.alive) continue;

    // Colisión con otras serpientes (salir tan pronto se encuentre una colisión)
    for (const otherId in players) {
      if (otherId === playerId) continue;
      const otherSnake = players[otherId].snake;
      for (const segment of otherSnake) {
        if (segment.x === head.x && segment.y === head.y) {
          player.alive = false;
          break;
        }
      }
      if (!player.alive) break;
    }
    if (!player.alive) continue;

    // Mueve la serpiente: añade la nueva cabeza
    snake.unshift(head);

    // Verifica colisión con la comida
    if (head.x === food.x && head.y === food.y) {
      player.score += 10 * player.pointsMultiplier;
      game.food = generateFood(players);
      if (!game.powerUp && Math.random() < POWER_UP_SPAWN_CHANCE) {
        game.powerUp = generatePowerUp(players);
      }
    } else {
      snake.pop();
    }

    // Verifica colisión con un power-up
    if (game.powerUp && head.x === game.powerUp.x && head.y === game.powerUp.y) {
      applyPowerUp(roomId, playerId, game.powerUp.type);
      game.powerUp = null;
      if (Math.random() < POWER_UP_SPAWN_CHANCE) {
        game.powerUp = generatePowerUp(players);
      }
    }
  }

  // Verifica si todos los jugadores murieron
  let allDead = Object.values(players).every(p => !p.alive);
  if (allDead && Object.keys(players).length > 0) {
    clearInterval(game.gameInterval);
    game.active = false;
    io.to(roomId).emit('gameOver');
  } else {
    // Emite el estado actualizado (se podría optimizar enviando solo deltas)
    io.to(roomId).emit('gameState', {
      players: players,
      food: game.food,
      obstacles: game.obstacles,
      powerUp: game.powerUp
    });
  }
}

// Genera un power-up (utiliza la lógica de la comida para posicionarlo)
function generatePowerUp(players) {
  if (Math.random() > POWER_UP_SPAWN_CHANCE) return null;
  const position = generateFood(players);
  const types = Object.values(POWER_UP_TYPES);
  const type = types[Math.floor(Math.random() * types.length)];
  return { x: position.x, y: position.y, type: type };
}

// Aplica los efectos del power-up y notifica a los clientes
function applyPowerUp(roomId, playerId, powerUpType) {
  const game = games[roomId];
  const player = game.players[playerId];
  switch (powerUpType) {
    case POWER_UP_TYPES.SPEED:
      player.speedMultiplier = 2;
      break;
    case POWER_UP_TYPES.SLOW:
      for (const id in game.players) {
        if (id !== playerId) game.players[id].speedMultiplier = 0.5;
      }
      break;
    case POWER_UP_TYPES.INVINCIBLE:
      player.invincible = true;
      break;
    case POWER_UP_TYPES.DOUBLE_POINTS:
      player.pointsMultiplier = 2;
      break;
  }
  setTimeout(() => {
    if (!game.players[playerId]) return;
    switch (powerUpType) {
      case POWER_UP_TYPES.SPEED:
        player.speedMultiplier = 1;
        break;
      case POWER_UP_TYPES.SLOW:
        for (const id in game.players) {
          if (id !== playerId) game.players[id].speedMultiplier = 1;
        }
        break;
      case POWER_UP_TYPES.INVINCIBLE:
        player.invincible = false;
        break;
      case POWER_UP_TYPES.DOUBLE_POINTS:
        player.pointsMultiplier = 1;
        break;
    }
  }, POWER_UP_DURATION);
  io.to(roomId).emit('powerUpCollected', {
    playerId: playerId,
    type: powerUpType,
    duration: POWER_UP_DURATION
  });
}

// Manejo de conexiones WebSocket
io.on('connection', (socket) => {
  console.log('Conexión:', socket.id);

  socket.on('joinRoom', ({ roomId, playerName }) => {
    socket.join(roomId);
    if (!games[roomId]) {
      createGame(roomId);
    }
    createPlayer(roomId, socket.id, playerName);
    socket.emit('gameState', {
      players: games[roomId].players,
      food: games[roomId].food,
      obstacles: games[roomId].obstacles,
      powerUp: games[roomId].powerUp
    });
    socket.to(roomId).emit('playerJoined', { id: socket.id, name: playerName });
    if (!games[roomId].active) {
      games[roomId].active = true;
      games[roomId].gameInterval = setInterval(() => { updateGame(roomId); }, GAME_SPEED);
    }
  });

  socket.on('changeDirection', (direction) => {
    const rooms = Array.from(socket.rooms);
    const roomId = rooms.find(r => r !== socket.id);
    if (roomId && games[roomId] && games[roomId].players[socket.id]) {
      const currentDir = games[roomId].players[socket.id].direction;
      if (
        (direction === 'up' && currentDir !== 'down') ||
        (direction === 'down' && currentDir !== 'up') ||
        (direction === 'left' && currentDir !== 'right') ||
        (direction === 'right' && currentDir !== 'left')
      ) {
        games[roomId].players[socket.id].direction = direction;
      }
    }
  });

  socket.on('disconnect', () => {
    console.log('Desconexión:', socket.id);
    for (const roomId in games) {
      if (games[roomId].players[socket.id]) {
        delete games[roomId].players[socket.id];
        socket.to(roomId).emit('playerLeft', socket.id);
        if (Object.keys(games[roomId].players).length === 0) {
          if (games[roomId].gameInterval) clearInterval(games[roomId].gameInterval);
          delete games[roomId];
          console.log(`Sala ${roomId} cerrada`);
        }
        break;
      }
    }
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Servidor corriendo en el puerto ${PORT}`);
});
