"""Random bot: choose one legal move at random."""

import random

from engine.base_bot import BaseBot


class Bot(BaseBot):
    name = "Random"

    def choose_move(self, board):
        # Ask the helper for moves that are allowed in this position.
        moves = self.get_legal_moves(board)

        # Pick one move from the list. This bot does not look for good moves.
        return random.choice(moves)
