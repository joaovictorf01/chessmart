# coding: utf-8
# pyright: basic

# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""Games from lichess.org, as PGN with the clock of every move.

What the user types can be a game link, a game id or a Lichess username (the
last game of that player). The export asks for clocks and leaves out
Lichess's own evaluations: on the analysis board the engine answers the
player, it does not speak first. Free of NVDA imports; the network call runs
on a worker thread.
"""

import datetime
import io
import re
import typing as t
import urllib.error
import urllib.parse
import urllib.request

from .game_tree import record_filename
from .paths import import_bundled
from .tactic.download import DownloadError, close_http_error


with import_bundled():
	import chess.pgn


# Lichess answers the user-games export with 404 to clients that do not look
# like a browser; a browser-like agent, still naming the add-on, is accepted.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) chessmart-nvda-addon"
BASE = "https://lichess.org"
EXPORT_OPTIONS = {"clocks": "true", "evals": "false", "opening": "true"}

_GAME_ID = re.compile(r"[A-Za-z0-9]{8}")
_USERNAME = re.compile(r"[A-Za-z0-9_-]{2,30}")
# Site pages whose name has the length of a game id.
_SITE_PAGES = {"training", "practice", "analysis", "streamer", "insights", "simul", "tournament", "broadcast"}


class GameRef(t.NamedTuple):
	kind: str  # "game" or "user"
	value: str


def parse_reference(text: str) -> t.Optional[GameRef]:
	"""What the user typed, as a game id or a username; None if it is neither.

	Accepted: `https://lichess.org/o9PtYEji`, `lichess.org/o9PtYEjiXyZw/black`
	(the 12-character player link), `o9PtYEji`, `@victorf01`, `victorf01`,
	`lichess.org/@/victorf01`. A bare word of 8 letters and digits is read as
	a game id, since that is what a link holds; a username of exactly 8
	characters needs the @.
	"""
	text = text.strip()
	if not text:
		return None
	if "lichess.org/" in text:
		path = text.split("lichess.org/", 1)[1].split("?", 1)[0].split("#", 1)[0]
		first = path.strip("/").split("/", 1)[0]
		if first == "@":
			user = path.strip("/").split("/")[1] if "/" in path.strip("/") else ""
			return GameRef("user", user) if _USERNAME.fullmatch(user) else None
		if first.lower() in _SITE_PAGES:
			return None
		if len(first) in (8, 12) and _GAME_ID.fullmatch(first[:8]):
			return GameRef("game", first[:8])
		return None
	if text.startswith("@"):
		user = text[1:]
		return GameRef("user", user) if _USERNAME.fullmatch(user) else None
	if _GAME_ID.fullmatch(text):
		return GameRef("game", text)
	if _USERNAME.fullmatch(text):
		return GameRef("user", text)
	return None


def export_url(ref: GameRef) -> str:
	query = urllib.parse.urlencode(EXPORT_OPTIONS)
	if ref.kind == "game":
		return f"{BASE}/game/export/{ref.value}?{query}"
	return f"{BASE}/api/games/user/{urllib.parse.quote(ref.value)}?max=1&{query}"


def fetch_game(ref: GameRef, timeout: float = 30.0, base: str = BASE) -> "chess.pgn.Game":
	"""Downloads and parses the game; DownloadError says why it could not."""
	url = export_url(ref).replace(BASE, base, 1)
	request = urllib.request.Request(
		url,
		headers={"User-Agent": USER_AGENT, "Accept": "application/x-chess-pgn"},
	)
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:
			text = response.read().decode("utf-8", errors="replace")
	except urllib.error.HTTPError as error:
		close_http_error(error)
		if error.code == 404:
			raise DownloadError("not found") from error
		raise DownloadError(f"HTTP {error.code}") from error
	except (urllib.error.URLError, OSError) as error:
		raise DownloadError(str(error)) from error
	game = chess.pgn.read_game(io.StringIO(text))
	if game is None or not text.strip():
		raise DownloadError("no game")
	return game


def imported_filename(game: "chess.pgn.Game") -> str:
	"""`2026-09-22_Gryniu696-vs-victorf01_lichess-o9PtYEji.pgn`: the game id makes a second import find the first."""
	headers = game.headers
	date_text = headers.get("UTCDate") or headers.get("Date") or ""
	try:
		date = datetime.datetime.strptime(date_text, "%Y.%m.%d").date()
	except ValueError:
		date = datetime.date.today()
	name = record_filename(date, headers.get("White", ""), headers.get("Black", ""))
	game_id = headers.get("GameId") or headers.get("Site", "").rsplit("/", 1)[-1]
	if _GAME_ID.fullmatch(game_id):
		name = name[: -len(".pgn")] + f"_lichess-{game_id}.pgn"
	return name
