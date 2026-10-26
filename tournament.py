"""Run every distinct pair of discovered bots in both colours."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import chess

import settings
from engine.bot_loader import BotSpec, discover_bots
from engine.game import Game


def play_game(
    white: BotSpec, black: BotSpec, timeout_seconds: float, games_dir: Path
) -> Game:
    """Play a game to completion and save its PGN."""
    game = Game(white, black, timeout_seconds)
    while game.result is None:
        game.play_bot_turn()
    games_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{white.file_path.stem}_vs_{black.file_path.stem}.pgn"
    game.save_pgn(str(games_dir / filename))
    return game


def run_tournament(
    bot_directory: str | Path = "bots",
    games_directory: str | Path = "games",
    timeout_seconds: float = settings.BOT_TIMEOUT_SECONDS,
) -> dict[str, float]:
    """Play all bot pairs with each bot playing both white and black."""
    discovery = discover_bots(bot_directory)
    for error in discovery.errors:
        print(f"Could not load {error.file_path.name}: {error.message}")
    if len(discovery.bots) < 2:
        raise ValueError("A tournament needs at least two valid bots.")

    scores: dict[str, float] = defaultdict(float)
    games_dir = Path(games_directory)
    for index, first in enumerate(discovery.bots):
        for second in discovery.bots[index + 1 :]:
            for white, black in ((first, second), (second, first)):
                game = play_game(white, black, timeout_seconds, games_dir)
                if game.result is None:
                    raise RuntimeError("Game ended without a result.")
                if game.result.result == "1-0":
                    scores[white.name] += 1
                elif game.result.result == "0-1":
                    scores[black.name] += 1
                else:
                    scores[white.name] += 0.5
                    scores[black.name] += 0.5
                print(
                    f"{white.name} vs {black.name}: {game.result.result} "
                    f"({game.result.reason})"
                )
    return dict(scores)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bots", default="bots", help="Folder containing bot files.")
    parser.add_argument("--games", default="games", help="Folder for saved PGN records.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=settings.BOT_TIMEOUT_SECONDS,
        help="Per-move safety limit in seconds (default: settings.py).",
    )
    args = parser.parse_args()

    scores = run_tournament(args.bots, args.games, args.timeout)
    print("\nLeague table")
    print("------------")
    for name, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        print(f"{name:<20} {score:g}")


if __name__ == "__main__":
    main()
