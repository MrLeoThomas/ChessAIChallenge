# Chess AI Classroom

A classroom chess app where students write one Python file to create a bot.
The engine uses `python-chess` for legal moves and chess rules, and `pygame`
for the board and menus. Games have no chess clock. A hidden safety limit
stops a bot process that does not respond.

## Install and run

Python 3.10 or later is required.

1. Open a terminal in this project folder.
2. Create and activate a virtual environment:

   ```sh
   python -m venv .venv
   ```

   On Windows, use `.venv\Scripts\activate`. On macOS or Linux, use
   `source .venv/bin/activate`.
3. Install packages:

   ```sh
   python -m pip install -r requirements.txt
   ```
4. Start the graphical app:

   ```sh
   python main.py
   ```

Choose 1-player mode to play against a bot, or 0-player mode to watch two bots.
Use the menu to select bots and your colour. In a game, click a piece and its
destination, or drag the piece. Legal squares are highlighted. Select a
promotion piece when asked. Press Escape to return to the menu.

For bot-versus-bot games, Pause/Resume and Step control play. Adjust the delay
with the slider or the left/right arrow keys; the delay affects display only.

## Your first bot

1. Open `bots/` and make a copy of `random_bot.py`, named for example
   `my_bot.py`.
2. Edit only your copy. Keep the class named `Bot`, give it a unique `name`,
   and implement `choose_move(self, board)`.
3. For a simple first move choice, use
   `return self.get_legal_moves(board)[0]`.
4. Run `python main.py`. Your bot should appear in the menu. You can also run
   `python tournament.py` to test all bots together.
5. Read [BOT_HELPERS.md](./BOT_HELPERS.md) for the helper reference, examples,
   move notation, and ideas for improving your bot.

The bot receives a copy of the current board. Return a legal move string (for
example `"e2e4"`) or a `chess.Move`. The bot does not receive a time limit.
The app runs it in a separate process so an error or an infinite loop cannot
freeze the interface.

## Tournament and teacher settings

Run a round-robin tournament of all valid bot files, with each pair playing
both colours:

```sh
python tournament.py
```

The command prints a league table and saves each game as PGN in `games/`.
Choose folders or a different per-move safety limit with:

```sh
python tournament.py --bots bots --games games --timeout 30
```

The default safety limit is `BOT_TIMEOUT_SECONDS` in `settings.py`. This is a
teacher safety setting, not a chess clock: students do not see it, and their
`choose_move` method has no time parameter. Increase it for slower classroom
computers or bots that search more deeply. Each game also reports the reason
it ended; invalid moves, exceptions, wrong return types, and timeouts lose.

## Tests

Install pytest if it is not already installed, then run:

```sh
python -m pip install pytest
python -m pytest
```

The tests cover helper methods, bot discovery, game results, and failing or
unresponsive bot processes.

## Project folders

```text
main.py                 Graphical app entry point
settings.py             Teacher safety setting
engine/                 Bot helpers, loader, safe runner, game controller
gui/                    Pygame menus and board
gui/assets/pieces/       White and black chess piece images
bots/                   Example bots and student bot files
games/                  Saved PGN records
tests/                  Automated tests
tournament.py           Headless round-robin tournament
BOT_HELPERS.md           Student helper reference
BOT_HELPERS.pdf          Printable helper reference
```
