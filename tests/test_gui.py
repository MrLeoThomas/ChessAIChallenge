import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess
import pygame

from engine.bot_loader import discover_bots
from engine.game import Game, HumanPlayer
from gui.app import ChessApp, WINDOW_HEIGHT, WINDOW_WIDTH


def make_app():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    app = ChessApp(screen, discover_bots("bots"))
    app.mode = 0
    app.game = Game(HumanPlayer(), app.bots[0])
    return app


def test_board_click_moves_human_piece():
    app = make_app()
    origin = app._square_rect(chess.E2).center
    destination = app._square_rect(chess.E4).center
    app._mouse_down(origin)
    app._mouse_down(destination)
    assert app.game.board.peek() == chess.Move.from_uci("e2e4")
    assert not app._human_turn()
    pygame.quit()


def test_human_promotion_shows_choices_and_applies_selected_piece():
    app = make_app()
    app.game.board.set_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    app._mouse_down(app._square_rect(chess.A7).center)
    app._mouse_down(app._square_rect(chess.A8).center)
    assert len(app.promotion_moves) == 4
    app._promotion_click((367, 385))
    assert app.game.board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)
    assert not app.promotion_moves
    pygame.quit()


def test_menu_starts_human_vs_bot_game():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    app = ChessApp(screen, discover_bots("bots"))
    app._menu_click((500, 245 + 4 * 72 + 20))
    assert app.game is not None
    assert isinstance(app.game.players[chess.WHITE], HumanPlayer)
    pygame.quit()


def test_bot_vs_bot_step_runs_asynchronously_and_pauses():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    app = ChessApp(screen, discover_bots("bots"))
    app.mode = 1
    app._start_game()
    app.paused = True
    app._update_game()
    assert not app.bot_thinking

    app.step_requested = True
    started = time.monotonic()
    app._update_game()
    assert app.bot_thinking
    assert time.monotonic() - started < 0.1

    deadline = time.monotonic() + 8
    while app.game.board.ply() == 0 and time.monotonic() < deadline:
        app._update_game()
        time.sleep(0.01)
    assert app.game.board.ply() == 1
    assert app.paused
    assert not app.bot_thinking
    pygame.quit()
