# Manual checks in NVDA

What the unit tests cannot see. After a change, run the parts it touches, with the add-on linked into NVDA (see CONTRIBUTING.md) and plugins reloaded with NVDA+Control+F3.

## Any board

- Arrows move one square and stop at the edge with a sound; the square and piece are spoken.
- Enter on a piece, Enter on a destination: the move is spoken; a pawn to the last rank asks for the piece.
- A, M, F1, F3, F4 speak; Escape in the score sheet returns to the board.
- Escape on the board asks first when something would be lost, and closes the window.
- The board picture follows the focus after a fast run of arrows.

## Game against the computer

- The engine answers; at the chosen strength it does not play instantly perfect moves.
- Control+S saves a PGN; Control+Shift+S saves a picture.

## Tactics

- The first move is played and spoken; the goal is said.
- A wrong move says so and settles the rating; the puzzle goes on.
- Control+H three times: themes, origin, destination.
- Control+N once mid-puzzle asks for a second press; twice skips.
- Control+R restarts, and the retry is not rated. Tab opens the actions bar; Escape returns.

## Endgames

- The question (win, draw, loss) comes first; the answer is judged.
- A spoiled move is announced by the judge; Backspace takes back.
- Control+T and Control+Shift+T give hints; the end says hints count as practice.
- Control+N goes to the next position. Tab opens the actions bar.

## Analysis board

- Moves for both sides; going back with Alt+Left and playing another move says "new variation".
- Alt+Up leaves the variation; Alt+Down lists the moves recorded.
- C writes a comment, Shift+C reads it; Control+1 to 6 mark, spoken in words.
- E speaks an evaluation; E twice thinks longer; Shift+E reviews the move; Control+E adds the engine line.
- A named opening is spoken; O repeats it; "out of theory" after the last book move.
- Control+S asks for the headers and says the file name; the file opens again with Analyse PGN File.

## Board editor

- Shift+K on e1 says "white king, e1"; k on e8 "black king, e8"; Delete empties; Enter says the square.
- Tab: switch whose move, a castling right (and "not possible" without king and rook), check the position, analyse.
- Control+C then Control+V round-trips the position; a non-FEN on the clipboard is refused.
- Escape with pieces on the board asks first.

## Lichess import

- Tools > Chessmart > Import Lichess Game: a link, a code, a username; the game opens and says its opening and clock on each move.
- T sums up both clocks. Importing the same game again says it opens your copy.
- A wrong code or no connection says why, in a message.

## Downloads

- Progress is spoken every ten percent; Escape cancels; the next download resumes.
