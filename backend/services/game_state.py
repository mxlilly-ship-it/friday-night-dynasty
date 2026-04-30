import json
from typing import Any, Dict

from engine.game_engine import Game


def serialize_game(game: Game) -> Dict[str, Any]:
    # Game is a regular class; its state lives in __dict__.
    return dict(game.__dict__)


def deserialize_game(data: Dict[str, Any]) -> Game:
    game = Game()
    for k, v in data.items():
        setattr(game, k, v)
    return game


def dumps_game(game: Game) -> str:
    return json.dumps(serialize_game(game))


def loads_game(s: str) -> Game:
    return deserialize_game(json.loads(s))

