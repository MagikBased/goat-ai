"""Show the API's explicit incomplete status without simulating a fake duel."""

from goat_ai.engine import SimulatorUnavailable
from goat_ai.environments import GoatEnvironment

env = GoatEnvironment("decks/goat_control.ydk", "decks/chaos_turbo.ydk", seed=42)
try:
    env.reset()
except SimulatorUnavailable as exc:
    print(exc)

