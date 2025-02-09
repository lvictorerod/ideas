#!/usr/bin/env python3
import curses
import random
import json
import time
from pathlib import Path
from curses import KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN
from datetime import timedelta
from enum import IntEnum

# Constants
SAVE_FILE = Path.home() / ".2048_save"
STATS_FILE = Path.home() / ".2048_stats"
GRID_SIZE = 4
MAX_UNDO = 10

# Color scheme with background gradients
COLOR_SCHEME = {
    0: {'fg': curses.COLOR_BLACK, 'bg': 235},    # Dark gray
    2: {'fg': curses.COLOR_BLACK, 'bg': 231},    # White
    4: {'fg': curses.COLOR_BLACK, 'bg': 223},    # Light yellow
    8: {'fg': curses.COLOR_BLACK, 'bg': 215},    # Orange
    16: {'fg': curses.COLOR_BLACK, 'bg': 209},   # Light red
    32: {'fg': curses.COLOR_WHITE, 'bg': 203},   # Pink
    64: {'fg': curses.COLOR_WHITE, 'bg': 197},   # Red
    128: {'fg': curses.COLOR_WHITE, 'bg': 178},  # Yellow
    256: {'fg': curses.COLOR_WHITE, 'bg': 142},  # Light green
    512: {'fg': curses.COLOR_WHITE, 'bg': 106},  # Green
    1024: {'fg': curses.COLOR_WHITE, 'bg': 69},  # Cyan
    2048: {'fg': curses.COLOR_WHITE, 'bg': 33},  # Blue
    4096: {'fg': curses.COLOR_WHITE, 'bg': 127}, # Magenta
    8192: {'fg': curses.COLOR_WHITE, 'bg': 163}  # Purple
}


class Direction(IntEnum):
    LEFT = 0
    RIGHT = 1
    UP = 2
    DOWN = 3


class GameStats:
    """
    Tracks game statistics and persists them to disk.
    """
    def __init__(self):
        self.games_played = 0
        self.total_score = 0
        self.highest_tile = 0
        self.best_score = 0
        self.total_time_played = timedelta()
        self.longest_game = timedelta()
        self.achievements = set()
        self.load_stats()

    def load_stats(self):
        try:
            with open(STATS_FILE, 'r') as f:
                data = json.load(f)
                self.games_played = data.get('games_played', 0)
                self.total_score = data.get('total_score', 0)
                self.highest_tile = data.get('highest_tile', 0)
                self.best_score = data.get('best_score', 0)
                self.total_time_played = timedelta(seconds=data.get('total_time_played', 0))
                self.longest_game = timedelta(seconds=data.get('longest_game', 0))
                self.achievements = set(data.get('achievements', []))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_stats(self):
        data = {
            'games_played': self.games_played,
            'total_score': self.total_score,
            'highest_tile': self.highest_tile,
            'best_score': self.best_score,
            'total_time_played': int(self.total_time_played.total_seconds()),
            'longest_game': int(self.longest_game.total_seconds()),
            'achievements': list(self.achievements)
        }
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            curses.endwin()
            print(f"Error saving stats: {e}")

    def update_game_stats(self, game_state):
        self.games_played += 1
        self.total_score += game_state.score
        current_highest = max(max(row) for row in game_state.grid)
        self.highest_tile = max(self.highest_tile, current_highest)
        self.best_score = max(self.best_score, game_state.score)
        game_time = timedelta(seconds=int(game_state.elapsed_time))
        self.total_time_played += game_time
        self.longest_game = max(self.longest_game, game_time)
        self.achievements.update(game_state.achievements)
        self.save_stats()


class GameState:
    """
    Manages the game grid, moves, merging logic, persistence, and timer.
    """
    def __init__(self):
        self.init()
        self.stats = GameStats()

    def init(self):
        """Initializes a new game state."""
        self.grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.score = 0
        self.high_score = self.load_high_score()
        self.previous_states = []  # Stack for undo (max length = MAX_UNDO)
        self.start_time = time.time()
        self.elapsed_time = 0
        self.paused = False
        self.pause_start = None
        self.achievements = set()
        self.moves_count = 0
        self.merges_count = 0
        self.add_new_tile()
        self.add_new_tile()

    def load_high_score(self):
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('high_score', 0)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

    def save_game(self):
        data = {
            'grid': self.grid,
            'score': self.score,
            'high_score': max(self.score, self.high_score),
            'elapsed_time': self.elapsed_time,
            'moves_count': self.moves_count,
            'merges_count': self.merges_count,
            'achievements': list(self.achievements),
            'paused': self.paused
        }
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            curses.endwin()
            print(f"Error saving game: {e}")

    def load_game(self):
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                self.grid = data.get('grid', [[0] * GRID_SIZE for _ in range(GRID_SIZE)])
                self.score = data.get('score', 0)
                self.high_score = data.get('high_score', 0)
                self.elapsed_time = data.get('elapsed_time', 0)
                self.moves_count = data.get('moves_count', 0)
                self.merges_count = data.get('merges_count', 0)
                self.achievements = set(data.get('achievements', []))
                self.paused = data.get('paused', False)
                self.start_time = time.time() - self.elapsed_time
                if self.paused:
                    self.pause_start = time.time()
        except (FileNotFoundError, json.JSONDecodeError):
            self.init()

    def add_new_tile(self):
        """Adds a new tile (2 or 4) in a random empty cell."""
        empty_cells = [(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE) if self.grid[i][j] == 0]
        if empty_cells:
            i, j = random.choice(empty_cells)
            self.grid[i][j] = 2 if random.random() < 0.9 else 4

    def check_achievements(self):
        current_max = max(max(row) for row in self.grid)
        if current_max >= 2048 and "2048" not in self.achievements:
            self.achievements.add("2048")
        if current_max >= 4096 and "4096" not in self.achievements:
            self.achievements.add("4096")
        if self.score >= 10000 and "score_10k" not in self.achievements:
            self.achievements.add("score_10k")
        if self.moves_count >= 1000 and "moves_1k" not in self.achievements:
            self.achievements.add("moves_1k")

    def is_game_over(self):
        if any(0 in row for row in self.grid):
            return False
        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                current = self.grid[i][j]
                if j < GRID_SIZE - 1 and current == self.grid[i][j + 1]:
                    return False
                if i < GRID_SIZE - 1 and current == self.grid[i + 1][j]:
                    return False
        return True

    def move(self, direction):
        """Attempts a move in the specified direction. Returns True if the grid changed."""
        if self.paused:
            return False
        # Save current state for undo
        original_grid = [row.copy() for row in self.grid]
        original_score = self.score
        original_moves = self.moves_count
        original_merges = self.merges_count

        new_grid, score_delta, merges = self._calculate_move(direction)
        if new_grid != original_grid:
            self.previous_states.append((original_grid, original_score, original_moves, original_merges))
            if len(self.previous_states) > MAX_UNDO:
                self.previous_states.pop(0)
            self.grid = new_grid
            self.score += score_delta
            self.moves_count += 1
            self.merges_count += merges
            self.high_score = max(self.score, self.high_score)
            self.add_new_tile()
            self.check_achievements()
            return True
        return False

    def _calculate_move(self, direction):
        """
        Calculates the new grid after a move in the given direction.
        Uses helper functions for row reversal and transposition.
        """
        if direction == Direction.LEFT:
            return self._process_grid(self.grid)
        elif direction == Direction.RIGHT:
            reversed_grid = self.reverse_rows(self.grid)
            new_grid, score_delta, merges = self._process_grid(reversed_grid)
            return self.reverse_rows(new_grid), score_delta, merges
        elif direction == Direction.UP:
            transposed = self.transpose(self.grid)
            new_grid, score_delta, merges = self._process_grid(transposed)
            return self.transpose(new_grid), score_delta, merges
        elif direction == Direction.DOWN:
            # Reverse, transpose, process, then undo the transforms
            transposed_reversed = self.reverse_rows(self.transpose(self.grid))
            new_grid, score_delta, merges = self._process_grid(transposed_reversed)
            return self.transpose(self.reverse_rows(new_grid)), score_delta, merges
        return self.grid, 0, 0

    def _process_grid(self, grid):
        """
        Processes the entire grid by handling each row separately.
        Returns the new grid, the total score increment, and the merge count.
        """
        total_score = 0
        total_merges = 0
        new_grid = []
        for row in grid:
            new_row, score_delta, merge_count = self._process_row(row)
            total_score += score_delta
            total_merges += merge_count
            new_grid.append(new_row)
        return new_grid, total_score, total_merges

    def _process_row(self, row):
        """
        Processes a single row: compresses non-zero tiles and merges adjacent equal tiles.
        Returns the new row (with zeros padded), the score gained, and the number of merges.
        """
        new_row = []
        score_delta = 0
        merge_count = 0
        # Remove zeros from the row.
        nums = [n for n in row if n != 0]
        i = 0
        while i < len(nums):
            if i + 1 < len(nums) and nums[i] == nums[i + 1]:
                merged_value = nums[i] * 2
                new_row.append(merged_value)
                score_delta += merged_value
                merge_count += 1
                i += 2  # Skip the next tile as it has been merged.
            else:
                new_row.append(nums[i])
                i += 1
        # Pad the row with zeros to keep its length consistent.
        new_row.extend([0] * (GRID_SIZE - len(new_row)))
        return new_row, score_delta, merge_count

    @staticmethod
    def transpose(grid):
        """Returns the transposed grid."""
        return [list(row) for row in zip(*grid)]

    @staticmethod
    def reverse_rows(grid):
        """Returns a new grid with each row reversed."""
        return [row[::-1] for row in grid]

    def undo(self):
        if self.previous_states:
            prev_grid, prev_score, prev_moves, prev_merges = self.previous_states.pop()
            self.grid = prev_grid
            self.score = prev_score
            self.moves_count = prev_moves
            self.merges_count = prev_merges
            return True
        return False

    def pause(self):
        if not self.paused:
            self.paused = True
            self.pause_start = time.time()

    def unpause(self):
        if self.paused:
            self.paused = False
            pause_duration = time.time() - self.pause_start
            self.start_time += pause_duration
            self.pause_start = None

    def update_time(self):
        if not self.paused:
            self.elapsed_time = time.time() - self.start_time


class GameUI:
    """
    Handles drawing the game board, help, statistics screens,
    and processing user input via curses.
    """
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.game = GameState()
        self.help_mode = False
        self.stats_mode = False
        self.color_pair_map = {}
        self.setup_colors()

    def setup_colors(self):
        try:
            curses.start_color()
            curses.use_default_colors()
            sorted_values = sorted(COLOR_SCHEME.keys())
            for idx, value in enumerate(sorted_values):
                fg = COLOR_SCHEME[value]['fg']
                bg = COLOR_SCHEME[value]['bg']
                pair_number = idx + 1
                try:
                    curses.init_pair(pair_number, fg, bg)
                except curses.error:
                    # Fallback to basic colors if advanced colors are not supported.
                    curses.init_pair(pair_number, curses.COLOR_BLACK, curses.COLOR_WHITE)
                self.color_pair_map[value] = pair_number
        except curses.error as e:
            curses.endwin()
            print(f"Terminal does not support color: {e}")
            exit(1)

    def draw_tile(self, y, x, value):
        pair_number = self.color_pair_map.get(value, 1)
        self.stdscr.attron(curses.color_pair(pair_number))
        cell = f"{value:^6}" if value != 0 else " " * 6
        self.stdscr.addstr(y, x, cell)
        self.stdscr.attroff(curses.color_pair(pair_number))

    def draw_grid(self):
        h, w = self.stdscr.getmaxyx()
        if h < 20 or w < 50:  # Minimum size requirements
            self.stdscr.clear()
            msg = "Terminal too small - please resize"
            self.stdscr.addstr(0, 0, msg[:w-1])
            return

        self.stdscr.clear()
        # Update time before drawing the header.
        self.game.update_time()

        if self.help_mode:
            self.draw_help()
            return
        if self.stats_mode:
            self.draw_stats()
            return

        # Header
        header = "2048 Game"
        self.stdscr.addstr(1, (w - len(header)) // 2, header, curses.A_BOLD)
        # Scores
        self.stdscr.addstr(3, 2, f"Score: {self.game.score}")
        self.stdscr.addstr(3, w - 20, f"High Score: {self.game.high_score}")
        # Time and Moves
        time_str = str(timedelta(seconds=int(self.game.elapsed_time)))
        self.stdscr.addstr(4, 2, f"Time: {time_str}")
        self.stdscr.addstr(4, w - 20, f"Moves: {self.game.moves_count}")

        # Draw Grid Tiles
        for i, row in enumerate(self.game.grid):
            for j, val in enumerate(row):
                y_pos = i * 2 + 6
                x_pos = j * 8 + (w - (GRID_SIZE * 8)) // 2
                self.draw_tile(y_pos, x_pos, val)

        # Draw Achievements if any
        if self.game.achievements:
            y_pos = 15
            self.stdscr.addstr(y_pos, 2, "Achievements:", curses.A_BOLD)
            for i, achievement in enumerate(sorted(self.game.achievements)):
                self.stdscr.addstr(y_pos + 1 + i, 4, f"• {achievement}")

        # Controls Footer
        controls = "↑←↓→/WASD: Move | N: New | U: Undo | M: Save | L: Load | H: Help | P: Pause | T: Stats | Q: Quit"
        self.stdscr.addstr(h - 2, (w - len(controls)) // 2, controls)

        # Paused Overlay
        if self.game.paused:
            pause_msg = "GAME PAUSED - Press P to resume"
            self.stdscr.addstr(h // 2, (w - len(pause_msg)) // 2, pause_msg, curses.A_BOLD)

        # Game Over Overlay
        if self.game.is_game_over() and not self.game.paused:
            game_over_msg = "GAME OVER - Press N for New Game or Q to Quit"
            x_pos = self.center_x(game_over_msg, w)
            self.stdscr.addstr(h // 2 - 1, x_pos, game_over_msg, curses.A_BOLD)

    def draw_help(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        help_text = [
            "2048 Game Controls:",
            "",
            "Arrow Keys or WASD: Move tiles",
            "N: New Game",
            "U: Undo Move (up to 10 times)",
            "M: Save Game",
            "L: Load Game",
            "P: Pause/Resume",
            "H: Toggle Help",
            "T: Toggle Statistics",
            "Q: Quit Game",
            "",
            "How to play:",
            "Combine tiles with the same number to reach 2048!",
            "Each move adds a new tile (2 or 4).",
            "The game ends when no moves are possible.",
        ]
        for i, line in enumerate(help_text):
            self.stdscr.addstr(i + 1, (w - len(line)) // 2, line)
        self.stdscr.addstr(h - 2, (w - 20) // 2, "Press H to return", curses.A_BOLD)

    def draw_stats(self):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        stats = self.game.stats
        stats_text = [
            "Game Statistics:",
            "",
            f"Games Played: {stats.games_played}",
            f"Total Score: {stats.total_score}",
            f"Highest Tile: {stats.highest_tile}",
            f"Best Score: {stats.best_score}",
            f"Total Time Played: {stats.total_time_played}",
            f"Longest Game: {stats.longest_game}",
            "",
            "Achievements:",
        ]
        for i, line in enumerate(stats_text):
            self.stdscr.addstr(i + 1, (w - len(line)) // 2, line)
        # Display achievements if any
        if stats.achievements:
            y_start = len(stats_text) + 1
            for i, achievement in enumerate(sorted(stats.achievements)):
                self.stdscr.addstr(y_start + i, (w - len(achievement)) // 2, f"• {achievement}")
        else:
            self.stdscr.addstr(len(stats_text) + 1, (w - 20) // 2, "No achievements yet!")
        # Return instruction
        self.stdscr.addstr(h - 2, (w - 20) // 2, "Press T to return", curses.A_BOLD)

    def handle_input(self, key):
        direction_map = {
            KEY_UP: Direction.UP, ord('w'): Direction.UP, ord('W'): Direction.UP,
            KEY_DOWN: Direction.DOWN, ord('s'): Direction.DOWN, ord('S'): Direction.DOWN,
            KEY_LEFT: Direction.LEFT, ord('a'): Direction.LEFT, ord('A'): Direction.LEFT,
            KEY_RIGHT: Direction.RIGHT, ord('d'): Direction.RIGHT, ord('D'): Direction.RIGHT,
        }
        if key in direction_map:
            self.game.move(direction_map[key])
        elif key in (ord('q'), ord('Q')):
            if self.game.is_game_over() or self.confirm_quit():
                return False  # Signal to quit game
        elif key in (ord('n'), ord('N')):
            if self.game.is_game_over() or self.confirm_quit():
                self.game.init()  # Start a new game
        elif key in (ord('u'), ord('U')):
            self.game.undo()  # Undo last move
        elif key in (ord('m'), ord('M')):
            self.game.save_game()  # Save current game state
        elif key in (ord('l'), ord('L')):
            self.game.load_game()  # Load saved game state
        elif key in (ord('h'), ord('H')):
            self.help_mode = not self.help_mode  # Toggle help mode
        elif key in (ord('t'), ord('T')):
            self.stats_mode = not self.stats_mode  # Toggle statistics display
        elif key in (ord('p'), ord('P')):
            if self.game.paused:
                self.game.unpause()
            else:
                self.game.pause()
        return True

    def confirm_quit(self):
        h, w = self.stdscr.getmaxyx()
        confirm_msg = "Are you sure you want to quit? (Y/N)"
        self.stdscr.addstr(h // 2, (w - len(confirm_msg)) // 2, confirm_msg, curses.A_BOLD)
        self.stdscr.refresh()
        while True:
            key = self.stdscr.getch()
            if key in (ord('y'), ord('Y')):
                return True
            elif key in (ord('n'), ord('N')):
                return False

    def center_x(self, msg, width):
        return max(0, (width - len(msg)) // 2)

    def run(self):
        """Main loop: update game state, draw, and process input."""
        while True:
            self.draw_grid()
            key = self.stdscr.getch()
            if not self.handle_input(key):
                break


def main(stdscr):
    curses.curs_set(0)  # Hide the cursor
    game_ui = GameUI(stdscr)
    game_ui.run()


if __name__ == "__main__":
    curses.wrapper(main)
