"""Discover and validate student bots in the bots folder."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from engine.base_bot import BaseBot


@dataclass(frozen=True)
class BotSpec:
    """A validated bot class and the file that defines it."""

    name: str
    module_name: str
    file_path: Path
    bot_class: type[BaseBot]


@dataclass(frozen=True)
class BotLoadError:
    """A bot file that could not be imported or validated."""

    file_path: Path
    message: str


@dataclass
class BotDiscovery:
    bots: list[BotSpec]
    errors: list[BotLoadError]


def _import_file(path: Path) -> ModuleType:
    module_name = f"_student_bot_{path.stem}"
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError("Python could not create a module loader for this file.")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def discover_bots(directory: str | Path = "bots") -> BotDiscovery:
    """Load each Python bot file and report invalid files without stopping.

    Files beginning with an underscore and ``__init__.py`` are ignored.
    """
    bot_directory = Path(directory).resolve()
    bots: list[BotSpec] = []
    errors: list[BotLoadError] = []
    if not bot_directory.is_dir():
        return BotDiscovery(bots, [BotLoadError(bot_directory, "Bot folder does not exist.")])

    for path in sorted(bot_directory.glob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        try:
            module = _import_file(path)
            bot_class = getattr(module, "Bot", None)
            if not isinstance(bot_class, type) or not issubclass(bot_class, BaseBot):
                raise TypeError("File must define a Bot class that inherits from BaseBot.")
            if (
                bot_class is BaseBot
                or not callable(getattr(bot_class, "choose_move", None))
                or bot_class.choose_move is BaseBot.choose_move
            ):
                raise TypeError("Bot must implement choose_move(board).")
            name = getattr(bot_class, "name", path.stem)
            if not isinstance(name, str) or not name.strip():
                raise TypeError("Bot.name must be a non-empty string.")
            bots.append(BotSpec(name, f"_student_bot_{path.stem}", path, bot_class))
        except Exception as error:
            errors.append(BotLoadError(path, f"{type(error).__name__}: {error}"))
    return BotDiscovery(bots, errors)
