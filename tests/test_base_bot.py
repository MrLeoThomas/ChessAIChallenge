import chess

from engine.base_bot import BaseBot


class ExampleBot(BaseBot):
    def choose_move(self, board):
        return "e2e4"


def test_is_legal_accepts_uci_and_move_and_rejects_invalid():
    bot = ExampleBot()
    board = chess.Board()
    assert bot.is_legal(board, "e2e4")
    assert bot.is_legal(board, chess.Move.from_uci("e2e4"))
    assert not bot.is_legal(board, "e2-e4")
    assert not bot.is_legal(board, "e7e5")


def test_check_helper_and_board_are_unchanged():
    bot = ExampleBot()
    board = chess.Board("7k/8/8/8/8/8/6Q1/7K w - - 0 1")
    original = board.fen()
    assert bot.is_check(board, "g2g7")
    assert not bot.is_check(board, "not-a-move")
    assert board.fen() == original


def test_checkmate_helper_and_illegal_move():
    bot = ExampleBot()
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    original = board.fen()
    assert bot.is_check_mate(board, "f7g7")
    assert not bot.is_check_mate(board, "bad")
    assert board.fen() == original


def test_legal_moves_and_capture_detection_including_en_passant():
    bot = ExampleBot()
    board = chess.Board()
    moves = bot.get_legal_moves(board)
    assert "e2e4" in moves
    assert not bot.is_capture(board, "e2e4")
    capture_board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    assert bot.is_capture(capture_board, "e4d5")
    ep_board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert bot.is_capture(ep_board, "e5d6")
    assert not bot.is_capture(ep_board, "not-a-move")


def test_piece_values_empty_invalid_promotion_and_castling_moves():
    bot = ExampleBot()
    board = chess.Board()
    assert bot.piece_value(board, "e2") == 1
    assert bot.piece_value(board, "b1") == 3
    assert bot.piece_value(board, "a1") == 5
    assert bot.piece_value(board, "d1") == 9
    assert bot.piece_value(board, "e1") == 0
    assert bot.piece_value(board, "e4") == 0
    assert bot.piece_value(board, "z9") == 0

    promotion_board = chess.Board("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    assert bot.is_legal(promotion_board, "a7a8q")
    castle_board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert bot.is_legal(castle_board, "e1g1")
    assert bot.is_legal(castle_board, "e1c1")
