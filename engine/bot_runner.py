"""Run student bot code in a separate process with a safety timeout."""

from __future__ import annotations

import multiprocessing
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess

from engine.bot_loader import BotSpec


@dataclass(frozen=True)
class BotMoveResult:
    move: chess.Move | None
    error: str | None = None


def _stop_process(process: multiprocessing.Process) -> None:
    if process.is_alive():
        process.terminate()
    process.join(timeout=0.2)
    if process.is_alive():
        process.kill()
        process.join()


def _bot_worker(connection: Any, file_path: str, board: chess.Board) -> None:
    """Import and run a bot in a child process; send only serializable data."""
    try:
        import importlib.util

        path = Path(file_path)
        module_spec = importlib.util.spec_from_file_location(
            f"_student_bot_worker_{path.stem}", path
        )
        if module_spec is None or module_spec.loader is None:
            raise ImportError("Python could not load the bot file.")
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        bot = module.Bot()
        move = bot.choose_move(board)
        if isinstance(move, chess.Move):
            payload = ("move", move.uci())
        elif isinstance(move, str):
            payload = ("move", move)
        else:
            payload = (
                "error",
                f"Bot returned the wrong return type ({type(move).__name__}); "
                "return a move string or chess.Move.",
            )
        connection.send(payload)
    except BaseException:
        connection.send(("error", traceback.format_exc()))
    finally:
        connection.close()


def run_bot(
    bot: BotSpec, board: chess.Board, timeout_seconds: float
) -> BotMoveResult:
    """Ask a bot for a move, enforcing the timeout and legal-move contract."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero.")
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_bot_worker,
        args=(child_connection, str(bot.file_path), board.copy()),
        name=f"chess-bot-{bot.name}",
    )
    try:
        process.start()
    except Exception:
        parent_connection.close()
        child_connection.close()
        return BotMoveResult(None, traceback.format_exc())
    child_connection.close()
    try:
        if not parent_connection.poll(timeout_seconds):
            _stop_process(process)
            return BotMoveResult(None, f"bot did not respond within {timeout_seconds:g} seconds")
        try:
            status, value = parent_connection.recv()
        except EOFError:
            return BotMoveResult(None, "Bot process exited without returning a move.")
        process.join(timeout=0.2)
        if status == "error":
            return BotMoveResult(None, str(value))
        try:
            move = chess.Move.from_uci(value)
        except (ValueError, TypeError):
            return BotMoveResult(None, f"Bot returned an invalid move string: {value!r}")
        if move not in board.legal_moves:
            return BotMoveResult(None, f"Bot returned an illegal move: {value}")
        return BotMoveResult(move)
    finally:
        parent_connection.close()
        if process.is_alive():
            _stop_process(process)
