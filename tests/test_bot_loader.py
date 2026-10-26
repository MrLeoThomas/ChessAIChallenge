from pathlib import Path

from engine.bot_loader import discover_bots


def test_loader_finds_valid_bot_and_reports_bad_files(tmp_path: Path):
    (tmp_path / "good.py").write_text(
        "from engine.base_bot import BaseBot\n"
        "class Bot(BaseBot):\n"
        "    name = 'Good'\n"
        "    def choose_move(self, board): return 'e2e4'\n",
        encoding="utf-8",
    )
    (tmp_path / "bad.py").write_text("class Bot: pass\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("this is not valid Python!", encoding="utf-8")
    (tmp_path / "missing_move.py").write_text(
        "from engine.base_bot import BaseBot\nclass Bot(BaseBot): pass\n",
        encoding="utf-8",
    )
    discovery = discover_bots(tmp_path)
    assert [bot.name for bot in discovery.bots] == ["Good"]
    assert {error.file_path.name for error in discovery.errors} == {
        "bad.py",
        "broken.py",
        "missing_move.py",
    }
