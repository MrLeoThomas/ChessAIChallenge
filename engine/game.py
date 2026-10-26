"""Headless game controller shared by the tournament and future GUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import chess
import chess.pgn

from engine.bot_loader import BotSpec
from engine.bot_runner import run_bot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HumanPlayer:
    """A human player whose moves are supplied through ``Game.apply_move``."""

    name: str = "Human"


class GameResult:
    """The final result and the reason the game ended."""

    def __init__(self, result: str, reason: str, detail: str | None = None):
        self.result = result
        self.reason = reason
        self.detail = detail

    @property
    def winner(self) -> chess.Color | None:
        if self.result == "1-0":
            return chess.WHITE
        if self.result == "0-1":
            return chess.BLACK
        return None

    def __repr__(self) -> str:
        return (
            f"GameResult(result={self.result!r}, reason={self.reason!r}, "
            f"detail={self.detail!r})"
        )


class Game:
    """A game between two bots, or between bot turns called by a GUI."""

    def __init__(
        self,
        white: BotSpec | HumanPlayer,
        black: BotSpec | HumanPlayer,
        timeout_seconds: float = 30,
        board: chess.Board | None = None,
    ):
        self.players = {chess.WHITE: white, chess.BLACK: black}
        self.timeout_seconds = timeout_seconds
        self.board = board.copy() if board is not None else chess.Board()
        self.result: GameResult | None = None

    def play_bot_turn(self) -> chess.Move | None:
        """Run the current bot turn; failures immediately forfeit the game."""
        if self.result is not None:
            return None
        if self._update_finished_result():
            return None
        color = self.board.turn
        bot = self.players[color]
        if isinstance(bot, HumanPlayer):
            return None
        response = run_bot(bot, self.board, self.timeout_seconds)
        if response.error is not None:
            self.forfeit_bot(response.error)
            return None
        assert response.move is not None
        self.board.push(response.move)
        self._update_finished_result()
        return response.move

    def forfeit_bot(self, error: str) -> None:
        """End the current bot's turn as a loss and retain the error detail."""
        if self.result is not None or isinstance(self.players[self.board.turn], HumanPlayer):
            raise ValueError("Only the current bot can forfeit.")
        bot = self.players[self.board.turn]
        logger.error("%s forfeits: %s", bot.name, error)
        winner = not self.board.turn
        self.result = GameResult(
            "1-0" if winner else "0-1",
            self._failure_reason(error),
            f"{bot.name}: {error}",
        )

    def apply_move(self, move: chess.Move | str) -> bool:
        """Apply a legal move from a human or another trusted caller."""
        if self.result is not None:
            return False
        try:
            parsed = chess.Move.from_uci(move) if isinstance(move, str) else move
        except (ValueError, TypeError):
            return False
        if not isinstance(parsed, chess.Move) or parsed not in self.board.legal_moves:
            return False
        self.board.push(parsed)
        self._update_finished_result()
        return True

    @staticmethod
    def _failure_reason(error: str) -> str:
        if error.startswith("bot did not respond"):
            return "bot did not respond"
        if "illegal move" in error.lower() or "invalid move string" in error.lower():
            return "illegal move"
        if "returned " in error and "return a move" in error:
            return "wrong return type"
        return "bot crashed"

    def _update_finished_result(self) -> bool:
        if self.result is not None:
            return True
        if self.board.is_checkmate():
            winner = not self.board.turn
            self.result = GameResult(
                "1-0" if winner else "0-1", "checkmate"
            )
        elif self.board.is_stalemate():
            self.result = GameResult("1/2-1/2", "stalemate")
        elif self.board.is_insufficient_material():
            self.result = GameResult("1/2-1/2", "insufficient material")
        elif self.board.is_seventyfive_moves():
            self.result = GameResult("1/2-1/2", "75-move rule")
        elif self.board.is_fivefold_repetition():
            self.result = GameResult("1/2-1/2", "fivefold repetition")
        elif self.board.can_claim_fifty_moves():
            self.result = GameResult("1/2-1/2", "50-move rule")
        elif self.board.can_claim_threefold_repetition():
            self.result = GameResult("1/2-1/2", "draw by repetition")
        return self.result is not None

    def to_pgn(self) -> chess.pgn.Game:
        """Create a PGN record containing moves and result details."""
        record = chess.pgn.Game.from_board(self.board)
        record.headers["White"] = self.players[chess.WHITE].name
        record.headers["Black"] = self.players[chess.BLACK].name
        record.headers["Result"] = self.result.result if self.result else "*"
        if self.result:
            record.headers["Termination"] = self.result.reason
            if self.result.detail:
                record.headers["Annotator"] = self.result.detail
        return record

    def save_pgn(self, path: str, unfinished_reason: str | None = None) -> None:
        """Write this game as a UTF-8 PGN file."""
        record = self.to_pgn()
        if self.result is None and unfinished_reason:
            record.headers["Termination"] = unfinished_reason
        with open(path, "w", encoding="utf-8") as pgn_file:
            print(record, file=pgn_file, end="\n\n")
