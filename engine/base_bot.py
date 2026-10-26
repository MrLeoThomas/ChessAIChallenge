"""Student-facing base class and beginner chess helpers."""

from __future__ import annotations

from typing import TypeAlias

import chess

MoveInput: TypeAlias = str | chess.Move


class BaseBot:
    """Base class for student chess bots.

    Override :meth:`choose_move` and return a legal move such as ``"e2e4"``
    or a ``chess.Move``. The board given to the bot is a copy.
    """

    name = "Unnamed Bot"

    def choose_move(self, board: chess.Board) -> MoveInput:
        """Choose a legal move for the current position.

        Args:
            board: A copy of the current position. Do not rely on changes to
                this board being saved by the game.

        Returns:
            A legal UCI move string such as ``"e2e4"`` or a ``chess.Move``.

        Example:
            ``return self.get_legal_moves(board)[0]``
        """
        raise NotImplementedError("Your bot must implement choose_move(board).")

    @staticmethod
    def _legal_move(board: chess.Board, move: MoveInput) -> chess.Move | None:
        if not isinstance(move, (str, chess.Move)):
            return None
        try:
            parsed = chess.Move.from_uci(move) if isinstance(move, str) else move
        except (ValueError, TypeError):
            return None
        if parsed not in board.legal_moves:
            return None
        return parsed

    def is_legal(self, board: chess.Board, move: MoveInput) -> bool:
        """Say whether ``move`` is legal on ``board``.

        ``move`` can be a string such as ``"e2e4"`` or a ``chess.Move``.
        The board is not changed.

        Example: ``self.is_legal(board, "e2e4")`` returns ``True`` at the
        start of a game.
        """
        return self._legal_move(board, move) is not None

    def is_check(self, board: chess.Board, move: MoveInput) -> bool:
        """Say whether a legal ``move`` gives check to the other player.

        Returns ``False`` for an illegal or badly written move. The board is
        not changed.

        Example: ``self.is_check(board, "e2e4")`` is ``False`` at game start.
        """
        parsed = self._legal_move(board, move)
        if parsed is None:
            return False
        position = board.copy()
        position.push(parsed)
        return position.is_check()

    def is_check_mate(self, board: chess.Board, move: MoveInput) -> bool:
        """Say whether a legal ``move`` checkmates the other player.

        Returns ``False`` for an illegal or badly written move. The board is
        not changed.

        Example: ``self.is_check_mate(board, "f7g7")`` checks a candidate
        move; it returns ``True`` only if that move ends the game by mate.
        """
        parsed = self._legal_move(board, move)
        if parsed is None:
            return False
        position = board.copy()
        position.push(parsed)
        return position.is_checkmate()

    def get_legal_moves(self, board: chess.Board) -> list[str]:
        """Get every legal move as a string such as ``"e2e4"``.

        The board is not changed.

        Example: ``self.get_legal_moves(board)`` includes ``"e2e4"`` at the
        start of a game.
        """
        return [move.uci() for move in board.legal_moves]

    def is_capture(self, board: chess.Board, move: MoveInput) -> bool:
        """Say whether a legal ``move`` captures an opponent's piece.

        This also detects en passant. Returns ``False`` for an illegal or
        badly written move. The board is not changed.

        Example: ``self.is_capture(board, "e4d5")`` checks whether that move
        captures a piece in the current position.
        """
        parsed = self._legal_move(board, move)
        return parsed is not None and board.is_capture(parsed)

    def piece_value(self, board: chess.Board, square: str) -> int:
        """Get the simple value of the piece on a square.

        Values are pawn 1, knight 3, bishop 3, rook 5, queen 9 and king 0.
        An empty or invalid square has value 0.

        Example: ``self.piece_value(board, "e2")`` returns ``1`` at game start.
        """
        try:
            piece = board.piece_at(chess.parse_square(square))
        except (ValueError, TypeError):
            return 0
        if piece is None:
            return 0
        return {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0,
        }[piece.piece_type]
