import chess

from engine.bot_loader import BotSpec
from engine.game import Game, HumanPlayer


class SimpleBot:
    name = "Example"

    def choose_move(self, board):
        return "e2e4"


def spec(name="Example"):
    return BotSpec(name, "unused", __file__, SimpleBot)


def test_game_applies_legal_moves_and_saves_finished_result():
    game = Game(spec("White"), spec("Black"))
    assert game.apply_move("e2e4")
    assert game.board.peek() == chess.Move.from_uci("e2e4")
    assert not game.apply_move("e7-e5")
    game.board.set_fen("7k/6pp/8/8/8/8/5PPP/6K1 w - - 0 1")
    assert game.apply_move("f2f4")
    assert game.result is None


def test_game_detects_checkmate_and_draw_reasons():
    game = Game(spec("White"), spec("Black"))
    game.board.set_fen("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
    game._update_finished_result()
    assert game.result.reason == "checkmate"
    assert game.result.result == "1-0"

    draw_game = Game(spec(), spec())
    draw_game.board.set_fen("7k/8/8/8/8/8/8/K7 w - - 0 1")
    draw_game._update_finished_result()
    assert draw_game.result.reason == "insufficient material"


def test_game_can_hold_a_human_player():
    game = Game(HumanPlayer(), spec("Bot"))
    assert game.play_bot_turn() is None
    assert game.apply_move("e2e4")
    assert game.board.turn == chess.BLACK


def test_unfinished_game_can_be_saved_as_pgn(tmp_path):
    game = Game(HumanPlayer(), spec("Bot"))
    assert game.apply_move("e2e4")
    path = tmp_path / "unfinished.pgn"
    game.save_pgn(str(path), "unfinished")
    with path.open(encoding="utf-8") as stream:
        record = chess.pgn.read_game(stream)
    assert record.headers["Result"] == "*"
    assert record.headers["Termination"] == "unfinished"
    assert record.end().san() == "e4"
