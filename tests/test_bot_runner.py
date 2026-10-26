from pathlib import Path

from engine.base_bot import BaseBot
from engine.bot_loader import BotSpec
from engine.bot_runner import run_bot
from engine.game import Game
import chess


class PlaceholderBot(BaseBot):
    def choose_move(self, board):
        return "e2e4"


def make_spec(tmp_path: Path, source: str, name: str = "Test Bot") -> BotSpec:
    file_path = tmp_path / "bot.py"
    file_path.write_text(
        "from engine.base_bot import BaseBot\n"
        "class Bot(BaseBot):\n"
        "    name = 'Test Bot'\n"
        f"    def choose_move(self, board):\n        {source}\n",
        encoding="utf-8",
    )
    return BotSpec(name, "test_bot", file_path, PlaceholderBot)


def test_runner_accepts_a_legal_move(tmp_path):
    result = run_bot(make_spec(tmp_path, "return 'e2e4'"), chess.Board(), 5)
    assert result.error is None
    assert result.move == chess.Move.from_uci("e2e4")


def test_runner_reports_illegal_move_and_wrong_return_type(tmp_path):
    illegal = run_bot(make_spec(tmp_path, "return 'e7e5'"), chess.Board(), 5)
    assert illegal.move is None
    assert "illegal move" in illegal.error

    wrong_type = run_bot(make_spec(tmp_path, "return None"), chess.Board(), 5)
    assert wrong_type.move is None
    assert "wrong return type" in wrong_type.error


def test_runner_reports_exception_and_stops_unresponsive_bot(tmp_path):
    crashed = run_bot(make_spec(tmp_path, "raise RuntimeError('broken')"), chess.Board(), 5)
    assert crashed.move is None
    assert "RuntimeError: broken" in crashed.error

    unresponsive = run_bot(
        make_spec(tmp_path, "while True: pass"),
        chess.Board(),
        1.0,
    )
    assert unresponsive.move is None
    assert "did not respond" in unresponsive.error


def test_game_turns_bad_bot_responses_into_forfeits(tmp_path):
    bot = make_spec(tmp_path, "return 'e7e5'", "Illegal Bot")
    game = Game(bot, bot, timeout_seconds=5)
    assert game.play_bot_turn() is None
    assert game.result.result == "0-1"
    assert game.result.reason == "illegal move"
    assert "Illegal Bot" in game.result.detail
