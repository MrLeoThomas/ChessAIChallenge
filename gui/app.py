"""Pygame menus and interface for human-versus-bot and bot-versus-bot games."""

from __future__ import annotations

import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import chess
import pygame

import settings
from engine.bot_loader import BotDiscovery, BotSpec, discover_bots
from engine.bot_runner import BotMoveResult, run_bot
from engine.game import Game, HumanPlayer

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 720
BOARD_SIZE = 640
BOARD_LEFT = 32
BOARD_TOP = 40
SQUARE_SIZE = BOARD_SIZE // 8
BACKGROUND = (32, 39, 48)
PANEL = (45, 54, 64)
TEXT = (240, 241, 235)
MUTED = (179, 188, 194)
LIGHT_SQUARE = (235, 222, 199)
DARK_SQUARE = (113, 143, 123)
HIGHLIGHT = (232, 194, 75, 150)
CHECK = (210, 70, 65, 170)
PIECE_NAMES = {
    chess.KING: "king",
    chess.QUEEN: "queen",
    chess.ROOK: "rook",
    chess.BISHOP: "bishop",
    chess.KNIGHT: "knight",
    chess.PAWN: "pawn",
}


class ChessApp:
    """Own the UI state and ensure bot turns never block the event loop."""

    def __init__(self, screen: pygame.Surface, discovery: BotDiscovery):
        self.screen = screen
        self.discovery = discovery
        self.bots = discovery.bots
        self.mode = 0
        self.bot_indices = [0, min(1, max(0, len(self.bots) - 1))]
        self.human_color = chess.WHITE
        self.menu_focus = 0
        self.running = True
        self.game: Game | None = None
        self.selected_square: chess.Square | None = None
        self.drag_square: chess.Square | None = None
        self.mouse_position = (0, 0)
        self.promotion_moves: list[chess.Move] = []
        self.status_message = ""
        self.move_delay = 0.5
        self.paused = False
        self.step_requested = False
        self.last_move_at = 0.0
        self.last_move: chess.Move | None = None
        self.bot_queue: queue.Queue[BotMoveResult] = queue.Queue()
        self.bot_thinking = False
        self.move_log: list[str] = []
        self.saved_game = False
        self.scroll_offset = 0
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 22)
        self.small_font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 38, bold=True)
        piece_directory = Path(__file__).parent / "assets" / "pieces"
        self.piece_images = {
            (color, piece_type): pygame.transform.smoothscale(
                pygame.image.load(
                    str(piece_directory / f"{'white' if color else 'black'}_{name}.png")
                ).convert_alpha(),
                (SQUARE_SIZE, SQUARE_SIZE),
            )
            for color in (chess.WHITE, chess.BLACK)
            for piece_type, name in PIECE_NAMES.items()
        }

    def run(self) -> None:
        while self.running:
            self._events()
            if self.game is not None:
                self._update_game()
                self._save_finished_game()
                self._draw_game()
            else:
                self._draw_menu()
            pygame.display.flip()
            self.clock.tick(60)
        self._save_unfinished_game()

    def _events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._key_down(event)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse_position = event.pos
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._mouse_down(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._mouse_up(event.pos)
            elif event.type == pygame.MOUSEWHEEL and self.game is not None:
                self.scroll_offset = max(0, self.scroll_offset - event.y)

    def _key_down(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            if self.game is not None:
                self._save_unfinished_game()
                self.game = None
                self._reset_menu()
            else:
                self.running = False
        elif self.game is None:
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                self.menu_focus = (self.menu_focus + (1 if event.key == pygame.K_DOWN else -1)) % 5
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = 1 if event.key == pygame.K_RIGHT else -1
                self._change_menu_value(step)
            elif event.key == pygame.K_RETURN:
                if self.menu_focus == 4:
                    self._start_game()
                else:
                    self._change_menu_value(1)
        elif self.promotion_moves:
            if event.key in (pygame.K_q, pygame.K_r, pygame.K_b, pygame.K_n):
                choices = {
                    pygame.K_q: chess.QUEEN,
                    pygame.K_r: chess.ROOK,
                    pygame.K_b: chess.BISHOP,
                    pygame.K_n: chess.KNIGHT,
                }
                self._finish_move(next(
                    move for move in self.promotion_moves
                    if move.promotion == choices[event.key]
                ))
        elif self.game.result is None and self._is_bot_vs_bot():
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key == pygame.K_PERIOD:
                self.step_requested = True
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self.move_delay = max(
                    0.0, min(3.0, self.move_delay + (0.25 if event.key == pygame.K_RIGHT else -0.25))
                )

    def _reset_menu(self) -> None:
        self.selected_square = None
        self.drag_square = None
        self.promotion_moves.clear()
        self.status_message = ""
        self.bot_thinking = False
        self.move_log = []
        self.saved_game = False
        self.paused = False
        self.step_requested = False
        while not self.bot_queue.empty():
            self.bot_queue.get_nowait()

    def _change_menu_value(self, step: int) -> None:
        if not self.bots:
            return
        if self.menu_focus == 0:
            self.mode = (self.mode + step) % 2
        elif self.menu_focus in (1, 2):
            slot = self.menu_focus - 1
            self.bot_indices[slot] = (self.bot_indices[slot] + step) % len(self.bots)
        elif self.menu_focus == 3:
            self.human_color = not self.human_color

    def _mouse_down(self, position: tuple[int, int]) -> None:
        if self.game is None:
            self._menu_click(position)
            return
        if self.promotion_moves:
            self._promotion_click(position)
            return
        if self.game.result is not None:
            if pygame.Rect(730, 630, 230, 52).collidepoint(position):
                self.game = None
                self._reset_menu()
            return
        if self._is_bot_vs_bot():
            if pygame.Rect(694, 370, 90, 42).collidepoint(position):
                self.paused = not self.paused
            elif pygame.Rect(794, 370, 90, 42).collidepoint(position):
                self.step_requested = True
            elif pygame.Rect(694, 432, 280, 35).collidepoint(position):
                self.move_delay = max(
                    0.0,
                    min(3.0, (position[0] - 694) / 280 * 3.0),
                )
        square = self._square_at(position)
        if square is None or not self._human_turn():
            return
        if self.selected_square is not None and self._try_human_move(self.selected_square, square):
            return
        piece = self.game.board.piece_at(square)
        if piece is not None and piece.color == self.game.board.turn:
            self.selected_square = square
            self.drag_square = square

    def _mouse_up(self, position: tuple[int, int]) -> None:
        if self.game is None or self.promotion_moves or not self._human_turn():
            return
        destination = self._square_at(position)
        origin = self.drag_square
        self.drag_square = None
        if origin is not None and destination is not None and origin != destination:
            self._try_human_move(origin, destination)

    def _menu_click(self, position: tuple[int, int]) -> None:
        rows = [
            pygame.Rect(280, 245 + index * 72, 440, 56)
            for index in range(5)
        ]
        for index, rect in enumerate(rows):
            if rect.collidepoint(position):
                self.menu_focus = index
                if index == 4:
                    self._start_game()
                else:
                    self._change_menu_value(1)
                return

    def _start_game(self) -> None:
        if len(self.bots) < 1:
            self.status_message = "Add at least one valid bot file to the bots folder."
            return
        first = self.bots[self.bot_indices[0]]
        second = self.bots[self.bot_indices[1]]
        if self.mode == 0:
            human = HumanPlayer()
            white, black = (human, first) if self.human_color else (first, human)
        else:
            white, black = first, second
        self.game = Game(white, black, settings.BOT_TIMEOUT_SECONDS)
        self._reset_menu()
        self.last_move = None
        self.last_move_at = time.monotonic()

    def _is_bot_vs_bot(self) -> bool:
        return self.mode == 1

    def _human_turn(self) -> bool:
        if self.game is None or self.game.result is not None or self._is_bot_vs_bot():
            return False
        return isinstance(self.game.players[self.game.board.turn], HumanPlayer)

    def _update_game(self) -> None:
        assert self.game is not None
        if self.game.result is not None:
            return
        if self.bot_thinking:
            try:
                response = self.bot_queue.get_nowait()
            except queue.Empty:
                return
            self.bot_thinking = False
            if response.error:
                self.game.forfeit_bot(response.error)
                self.status_message = self.game.result.detail or response.error
            elif response.move is not None:
                move = response.move
                if self.game.apply_move(move):
                    self._record_move(move)
                    self.last_move = move
                    self.last_move_at = time.monotonic()
            return
        if self._human_turn():
            return
        if self._is_bot_vs_bot() and self.paused and not self.step_requested:
            return
        if self._is_bot_vs_bot() and not self.step_requested:
            if time.monotonic() - self.last_move_at < self.move_delay:
                return
        self.step_requested = False
        self._start_bot_worker()

    def _start_bot_worker(self) -> None:
        assert self.game is not None
        bot = self.game.players[self.game.board.turn]
        if isinstance(bot, HumanPlayer):
            return
        board = self.game.board.copy()
        timeout = self.game.timeout_seconds
        self.bot_thinking = True

        def calculate() -> None:
            try:
                self.bot_queue.put(run_bot(bot, board, timeout))
            except Exception as error:
                self.bot_queue.put(
                    BotMoveResult(None, f"Could not run bot process: {type(error).__name__}: {error}")
                )

        threading.Thread(target=calculate, name="chess-bot-turn", daemon=True).start()

    def _try_human_move(self, origin: chess.Square, destination: chess.Square) -> bool:
        assert self.game is not None
        choices = [
            move
            for move in self.game.board.legal_moves
            if move.from_square == origin and move.to_square == destination
        ]
        if not choices:
            return False
        if len(choices) > 1 and any(move.promotion for move in choices):
            self.promotion_moves = choices
            return True
        self._finish_move(choices[0])
        return True

    def _finish_move(self, move: chess.Move) -> None:
        assert self.game is not None
        self.promotion_moves.clear()
        self.selected_square = None
        self.drag_square = None
        if self.game.apply_move(move):
            self._record_move(move)
            self.last_move = move
            self.last_move_at = time.monotonic()

    def _record_move(self, move: chess.Move) -> None:
        assert self.game is not None
        number = self.game.board.fullmove_number
        notation = self.game.board.peek().uci()
        san_board = self.game.board.copy()
        san_board.pop()
        san = san_board.san(move)
        if self.game.board.turn == chess.BLACK:
            self.move_log.append(f"{number}. {san}")
        else:
            if self.move_log:
                self.move_log[-1] += f"  {san}"
            else:
                self.move_log.append(f"{number - 1}. ... {san}")
        if not san and notation:
            self.move_log.append(notation)

    def _save_finished_game(self) -> None:
        assert self.game is not None
        if self.game.result is None or self.saved_game:
            return
        folder = Path("games")
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        filename = f"game-{stamp}.pgn"
        self.game.save_pgn(str(folder / filename))
        self.saved_game = True
        self.status_message = (
            f"{self.game.result.result} — {self.game.result.reason}. "
            f"Saved {filename}"
        )

    def _save_unfinished_game(self) -> None:
        if self.game is None or self.saved_game or self.game.result is not None:
            return
        folder = Path("games")
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.game.save_pgn(str(folder / f"game-{stamp}.pgn"), "unfinished")
        self.saved_game = True

    def _square_at(self, position: tuple[int, int]) -> chess.Square | None:
        x, y = position
        if not (
            BOARD_LEFT <= x < BOARD_LEFT + BOARD_SIZE
            and BOARD_TOP <= y < BOARD_TOP + BOARD_SIZE
        ):
            return None
        file_index = (x - BOARD_LEFT) // SQUARE_SIZE
        row = (y - BOARD_TOP) // SQUARE_SIZE
        if self.human_color == chess.WHITE:
            rank = 7 - row
            file_index = file_index
        else:
            rank = row
            file_index = 7 - file_index
        return chess.square(file_index, rank)

    def _square_rect(self, square: chess.Square) -> pygame.Rect:
        file_index = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.human_color == chess.WHITE:
            column, row = file_index, 7 - rank
        else:
            column, row = 7 - file_index, rank
        return pygame.Rect(
            BOARD_LEFT + column * SQUARE_SIZE,
            BOARD_TOP + row * SQUARE_SIZE,
            SQUARE_SIZE,
            SQUARE_SIZE,
        )

    def _draw_menu(self) -> None:
        self.screen.fill(BACKGROUND)
        self._text("Chess AI Classroom", self.title_font, TEXT, (WINDOW_WIDTH // 2, 105), center=True)
        self._text(
            "Choose a mode and bot. Bots are loaded from the bots folder.",
            self.font,
            MUTED,
            (WINDOW_WIDTH // 2, 160),
            center=True,
        )
        values = [
            ("Mode", "1-player: You vs bot" if self.mode == 0 else "0-player: Bot vs bot"),
            ("Bot 1", self.bots[self.bot_indices[0]].name if self.bots else "No valid bots found"),
            ("Bot 2", self.bots[self.bot_indices[1]].name if self.bots else "No valid bots found"),
            ("Your colour", "White" if self.human_color else "Black"),
            ("Start", "Start game"),
        ]
        for index, (label, value) in enumerate(values):
            rect = pygame.Rect(280, 245 + index * 72, 440, 56)
            pygame.draw.rect(
                self.screen,
                (68, 91, 105) if self.menu_focus == index else PANEL,
                rect,
                border_radius=8,
            )
            self._text(f"{label}: {value}", self.font, TEXT, rect.center, center=True)
        self._text("Click a row to change it; choose Start to begin.", self.small_font, MUTED, (500, 610), center=True)
        self._text("Arrow keys change a selection; Enter activates it.", self.small_font, MUTED, (500, 635), center=True)
        if self.discovery.errors:
            self._text(
                f"{len(self.discovery.errors)} bot file(s) could not load; see the terminal output.",
                self.small_font,
                (255, 182, 100),
                (500, 662),
                center=True,
            )
        if not self.bots:
            self._text(self.status_message, self.small_font, (255, 150, 140), (500, 684), center=True)
        elif len(self.bots) == 1:
            self._text("Only one bot found: use 1-player mode or add another bot.", self.small_font, MUTED, (500, 684), center=True)

    def _draw_game(self) -> None:
        assert self.game is not None
        self.screen.fill(BACKGROUND)
        self._draw_board()
        self._draw_side_panel()
        if self.promotion_moves:
            self._draw_promotion_dialog()
        if self.game.result is not None:
            self._draw_result_overlay()

    def _draw_board(self) -> None:
        assert self.game is not None
        board = self.game.board
        checked_king = board.king(board.turn) if board.is_check() else None
        legal_targets: set[chess.Square] = set()
        if self.selected_square is not None:
            legal_targets = {
                move.to_square
                for move in board.legal_moves
                if move.from_square == self.selected_square
            }
        for rank in range(8):
            for file_index in range(8):
                square = chess.square(file_index, rank)
                rect = self._square_rect(square)
                color = LIGHT_SQUARE if (file_index + rank) % 2 else DARK_SQUARE
                pygame.draw.rect(self.screen, color, rect)
                if self.last_move and square in (
                    self.last_move.from_square,
                    self.last_move.to_square,
                ):
                    self._overlay(rect, HIGHLIGHT)
                if square == checked_king:
                    self._overlay(rect, CHECK)
                if square == self.selected_square:
                    pygame.draw.rect(self.screen, (250, 217, 94), rect, width=5)
                if square in legal_targets:
                    center = rect.center
                    pygame.draw.circle(self.screen, (42, 59, 52, 145), center, 11)
                piece = board.piece_at(square)
                if piece is not None and square != self.drag_square:
                    self._draw_piece(piece, rect.center)
                if chess.square_rank(square) == (0 if self.human_color else 7):
                    file_label = chess.FILE_NAMES[file_index]
                    label = self.small_font.render(file_label, True, (50, 58, 56))
                    self.screen.blit(label, (rect.right - 16, rect.bottom - 19))
                if chess.square_file(square) == (0 if self.human_color else 7):
                    rank_label = str(rank + 1)
                    label = self.small_font.render(rank_label, True, (50, 58, 56))
                    self.screen.blit(label, (rect.left + 4, rect.top + 2))
        if self.drag_square is not None:
            piece = board.piece_at(self.drag_square)
            if piece is not None:
                self._draw_piece(piece, self.mouse_position)

    def _draw_piece(self, piece: chess.Piece, center: tuple[int, int]) -> None:
        image = self.piece_images[piece.color, piece.piece_type]
        self.screen.blit(image, image.get_rect(center=center))

    def _draw_side_panel(self) -> None:
        assert self.game is not None
        pygame.draw.rect(self.screen, PANEL, pygame.Rect(690, 30, 285, 660), border_radius=12)
        for color, label in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
            player = self.game.players[color]
            player_name = getattr(player, "name", "Bot")
            active = self.game.board.turn == color and self.game.result is None
            fill = (70, 107, 88) if active else (61, 70, 79)
            pygame.draw.rect(self.screen, fill, pygame.Rect(712, 56 if color else 105, 240, 40), border_radius=6)
            self._text(f"{label}: {player_name}", self.small_font, TEXT, (722, 66 if color else 115))

        self._text("Moves", self.font, TEXT, (718, 176))
        move_area = pygame.Rect(710, 210, 245, 140)
        pygame.draw.rect(self.screen, (36, 43, 51), move_area, border_radius=6)
        visible = self.move_log[self.scroll_offset : self.scroll_offset + 7]
        for index, line in enumerate(visible):
            self._text(line, self.small_font, MUTED, (722, 219 + index * 18))

        if self._is_bot_vs_bot() and self.game.result is None:
            self._button("Pause" if not self.paused else "Resume", pygame.Rect(710, 370, 115, 42))
            self._button("Step", pygame.Rect(836, 370, 115, 42))
            self._text(f"Delay: {self.move_delay:.2f}s", self.small_font, TEXT, (714, 426))
            slider = pygame.Rect(710, 451, 240, 12)
            pygame.draw.rect(self.screen, (88, 100, 111), slider, border_radius=6)
            knob_x = slider.left + int(self.move_delay / 3.0 * slider.width)
            pygame.draw.circle(self.screen, (226, 195, 104), (knob_x, slider.centery), 10)
            self._text("Space pause · . step · ←/→ delay", self.small_font, MUTED, (710, 476))
        elif self.game.result is None:
            prompt = "Your move" if self._human_turn() else "Bot is thinking…"
            self._text(prompt, self.font, TEXT, (718, 385))
            self._text("Click or drag a piece to move.", self.small_font, MUTED, (718, 420))
        if self.status_message:
            self._wrapped_text(self.status_message, self.small_font, (255, 196, 130), pygame.Rect(710, 520, 245, 90))
        self._text("Esc: menu", self.small_font, MUTED, (718, 664))

    def _draw_promotion_dialog(self) -> None:
        assert self.game is not None
        shade = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 155))
        self.screen.blit(shade, (0, 0))
        panel = pygame.Rect(280, 285, 440, 150)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=12)
        self._text("Choose a promotion piece", self.font, TEXT, (500, 315), center=True)
        for index, piece_type in enumerate((chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)):
            move = next(m for m in self.promotion_moves if m.promotion == piece_type)
            rect = pygame.Rect(332 + index * 86, 350, 70, 70)
            pygame.draw.rect(self.screen, (74, 91, 102), rect, border_radius=8)
            piece = chess.Piece(piece_type, self.game.board.turn)
            self._draw_piece(piece, rect.center)
            self._text("QRBN"[index], self.small_font, MUTED, (rect.centerx, 428), center=True)

    def _promotion_click(self, position: tuple[int, int]) -> None:
        for index, piece_type in enumerate((chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)):
            rect = pygame.Rect(332 + index * 86, 350, 70, 70)
            if rect.collidepoint(position):
                move = next(m for m in self.promotion_moves if m.promotion == piece_type)
                self._finish_move(move)
                return

    def _draw_result_overlay(self) -> None:
        assert self.game is not None and self.game.result is not None
        shade = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 125))
        self.screen.blit(shade, (0, 0))
        panel = pygame.Rect(250, 245, 500, 230)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=14)
        self._text(
            f"Game over: {self.game.result.result}",
            self.title_font,
            TEXT,
            (500, 295),
            center=True,
        )
        self._wrapped_text(
            self.game.result.reason,
            self.font,
            TEXT,
            pygame.Rect(280, 335, 440, 42),
            center=True,
        )
        if self.game.result.detail:
            self._wrapped_text(
                self.game.result.detail,
                self.small_font,
                (255, 194, 155),
                pygame.Rect(280, 380, 440, 58),
                center=True,
            )
        self._button("Return to menu", pygame.Rect(385, 430, 230, 44))

    def _overlay(self, rect: pygame.Rect, color: tuple[int, ...]) -> None:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        layer.fill(color)
        self.screen.blit(layer, rect.topleft)

    def _button(self, label: str, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, (78, 111, 94), rect, border_radius=7)
        self._text(label, self.small_font, TEXT, rect.center, center=True)

    def _text(
        self,
        value: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        position: tuple[int, int],
        center: bool = False,
    ) -> None:
        image = font.render(value, True, color)
        rect = image.get_rect()
        if center:
            rect.center = position
        else:
            rect.topleft = position
        self.screen.blit(image, rect)

    def _wrapped_text(
        self,
        value: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        rect: pygame.Rect,
        center: bool = False,
    ) -> None:
        lines: list[str] = []
        current = ""
        for word in value.split():
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > rect.width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        for index, line in enumerate(lines[: max(1, rect.height // font.get_linesize())]):
            position = (rect.centerx, rect.top + index * font.get_linesize()) if center else (
                rect.left,
                rect.top + index * font.get_linesize(),
            )
            self._text(line, font, color, position, center=center)


def run() -> None:
    """Start the graphical app and report bot-loading problems in the terminal."""
    discovery = discover_bots("bots")
    for error in discovery.errors:
        print(f"Could not load {error.file_path.name}: {error.message}")
    pygame.init()
    pygame.display.set_caption("Chess AI Classroom")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    try:
        ChessApp(screen, discovery).run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    run()
