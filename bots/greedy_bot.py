"""Greedy bot: play checkmate if possible, otherwise take the best capture."""

import random

from engine.base_bot import BaseBot


class Bot(BaseBot):
    name = "Greedy"

    def choose_move(self, board):
        # First, look for a move that wins the game immediately.
        moves = self.get_legal_moves(board)
        for move in moves:
            if self.is_check_mate(board, move):
                return move

        # If there is no checkmate, find the capture with the highest value.
        best_capture = None
        best_value = 0
        for move in moves:
            if self.is_capture(board, move):
                destination = move[2:4]
                captured_value = self.piece_value(board, destination)

                # En passant captures a pawn, even though the destination is empty.
                if captured_value == 0:
                    captured_value = 1

                if captured_value > best_value:
                    best_capture = move
                    best_value = captured_value

        if best_capture is not None:
            return best_capture

        # If there are no useful captures, choose any legal move at random.
        return random.choice(moves)
