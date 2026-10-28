"""Check that a recorded decision sequence reproduces on a rules engine."""

from dataclasses import asdict, replace
from pathlib import Path

from goat_ai.engine.protocol import RulesEngine
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import Trajectory


class ReplayMismatch(ValueError):
    """A recorded trajectory differs from the engine at a decision or result."""


def verify_trajectory(trajectory: Trajectory, engine: RulesEngine,
                      deck_paths: tuple[str | Path, str | Path] | None = None) -> int:
    """Replay exact actions; return the number of verified decisions.

    ``deck_paths`` can relocate a trajectory's two YDK files. The caller must
    supply the same deck contents and pinned engine assets used for recording.
    Every observation and complete legal-action list is compared before an
    action is sent, so an unsupported native request cannot pass silently.
    """
    if trajectory.schema_version >= 18 and trajectory.terminal_observation is None:
        raise ReplayMismatch("schema v18 requires a terminal observation")
    if trajectory.ruleset != engine.ruleset.name:
        raise ReplayMismatch("ruleset differs from recorded trajectory")
    if trajectory.rules_profile is not None and trajectory.rules_profile != asdict(engine.ruleset):
        raise ReplayMismatch("rules profile differs from recorded trajectory")
    from goat_ai.environments import GoatEnvironment

    paths = deck_paths or trajectory.decks
    if trajectory.deck_sha256 is not None:
        try:
            hashes = tuple(sha256_file(path) for path in paths)
        except OSError as exc:
            raise ReplayMismatch(f"recorded deck file unavailable: {exc}") from exc
        if hashes != trajectory.deck_sha256:
            raise ReplayMismatch("deck contents differ from recorded trajectory")
    with GoatEnvironment(str(paths[0]), str(paths[1]), trajectory.seed, engine) as env:
        def without_equips(view):
            def cards(items):
                return tuple(replace(card, equipped_to=None) for card in items)

            return replace(view, hand=cards(view.hand), field=cards(view.field),
                           graveyards=tuple(cards(zone) for zone in view.graveyards),
                           banished=tuple(cards(zone) for zone in view.banished),
                           own_extra_deck=cards(view.own_extra_deck))

        def without_facedown_equips(view):
            return replace(view, field=tuple(
                replace(card, equipped_to=None) if card.position == "facedown" else card
                for card in view.field))

        def without_chain_targets(view):
            return replace(view, chain=tuple(replace(link, targets=())
                                             for link in view.chain))

        def without_races(view):
            def cards(items):
                return tuple(replace(card, race=None) for card in items)

            return replace(view, hand=cards(view.hand), field=cards(view.field),
                           graveyards=tuple(cards(zone) for zone in view.graveyards),
                           banished=tuple(cards(zone) for zone in view.banished),
                           own_extra_deck=cards(view.own_extra_deck))

        def without_summon_context(view):
            def cards(items):
                return tuple(replace(card, owner=None) for card in items)

            return replace(view, pending_summon=None,
                           hand=cards(view.hand), field=cards(view.field),
                           graveyards=tuple(cards(zone) for zone in view.graveyards),
                           banished=tuple(cards(zone) for zone in view.banished),
                           own_extra_deck=cards(view.own_extra_deck))

        def without_faceup_age(view):
            return replace(view, field=tuple(replace(card, faceup_turns=None)
                                             for card in view.field))

        observation = env.reset()
        for index, record in enumerate(trajectory.decisions):
            if env.is_terminal():
                raise ReplayMismatch(f"decision {index}: engine terminated early")
            compared_observation = observation
            recorded_observation = record.observation
            if trajectory.schema_version < 24:
                compared_observation = without_races(compared_observation)
                recorded_observation = without_races(recorded_observation)
            if trajectory.schema_version < 25:
                compared_observation = without_summon_context(compared_observation)
                recorded_observation = without_summon_context(recorded_observation)
            if trajectory.schema_version < 26:
                compared_observation = without_faceup_age(compared_observation)
                recorded_observation = without_faceup_age(recorded_observation)
            if trajectory.schema_version < 19:
                compared_observation = without_equips(compared_observation)
            elif trajectory.schema_version == 19:
                compared_observation = without_facedown_equips(compared_observation)
            if trajectory.schema_version < 21:
                compared_observation = without_chain_targets(compared_observation)
            if trajectory.schema_version < 22:
                compared_observation = replace(compared_observation, pending_attack=None)
            if trajectory.schema_version < 23:
                compared_observation = replace(compared_observation, turn_player=None)
            if trajectory.schema_version < 17:
                compared_observation = replace(compared_observation,
                                               known_opponent_hand_cards=())
            if trajectory.schema_version < 12:
                def old_cards(cards):
                    return tuple(replace(card, attack=None, defense=None, counters=())
                                 for card in cards)

                def old_view(view):
                    return replace(
                        view, hand=old_cards(view.hand), field=old_cards(view.field),
                        graveyards=tuple(old_cards(zone) for zone in view.graveyards),
                        banished=tuple(old_cards(zone) for zone in view.banished),
                        own_extra_deck=old_cards(view.own_extra_deck),
                    )

                compared_observation = old_view(compared_observation)
                recorded_observation = old_view(recorded_observation)
            if trajectory.schema_version < 11:
                compared_observation = replace(compared_observation, own_main_deck=())
            if trajectory.schema_version < 10:
                compared_observation = replace(compared_observation, private_reveals=())
            if trajectory.schema_version < 9:
                compared_observation = replace(compared_observation, disabled_zones=())
            if trajectory.schema_version < 8:
                compared_observation = replace(compared_observation, public_reveals=())
            if trajectory.schema_version < 7:
                compared_observation = replace(compared_observation, restrictions=())
            if trajectory.schema_version < 6:
                compared_observation = replace(compared_observation,
                                               known_opponent_field_cards=())
            if trajectory.schema_version < 5:
                compared_observation = replace(compared_observation, known_opponent_cards=())
            if trajectory.schema_version < 4:
                compared_observation = replace(compared_observation, public_history=())
            if compared_observation != recorded_observation:
                raise ReplayMismatch(f"decision {index}: observation differs")
            current_actions = env.legal_actions()
            compared_actions = (tuple(replace(action, kind="change_position")
                                      if action.kind == "flip_summon" else action
                                      for action in current_actions)
                                if trajectory.schema_version < 8 else current_actions)
            if compared_actions != record.legal_actions:
                raise ReplayMismatch(f"decision {index}: legal actions differ")
            observation = env.step(current_actions[record.legal_actions.index(
                record.selected_action)])
        if not env.is_terminal():
            raise ReplayMismatch("record ended before engine terminal state")
        if env.result() != trajectory.winner:
            raise ReplayMismatch("winner differs from recorded trajectory")
        terminal_observation = (without_equips(observation)
                                if trajectory.schema_version < 19 else
                                without_facedown_equips(observation)
                                if trajectory.schema_version == 19 else observation)
        if trajectory.schema_version < 24:
            terminal_observation = without_races(terminal_observation)
        if trajectory.schema_version < 25:
            terminal_observation = without_summon_context(terminal_observation)
        if trajectory.schema_version < 26:
            terminal_observation = without_faceup_age(terminal_observation)
        if trajectory.schema_version < 21:
            terminal_observation = without_chain_targets(terminal_observation)
        if trajectory.schema_version < 22:
            terminal_observation = replace(terminal_observation, pending_attack=None)
        if trajectory.schema_version < 23:
            terminal_observation = replace(terminal_observation, turn_player=None)
        recorded_terminal = trajectory.terminal_observation
        if trajectory.schema_version < 26 and recorded_terminal is not None:
            recorded_terminal = without_faceup_age(recorded_terminal)
        if trajectory.schema_version < 24 and recorded_terminal is not None:
            recorded_terminal = without_races(recorded_terminal)
        if trajectory.schema_version < 25 and recorded_terminal is not None:
            recorded_terminal = without_summon_context(recorded_terminal)
        if (trajectory.schema_version >= 18
                and recorded_terminal is not None
                and terminal_observation != recorded_terminal):
            fields = [name for name in vars(terminal_observation)
                      if getattr(terminal_observation, name) != getattr(
                          recorded_terminal, name)]
            raise ReplayMismatch(f"terminal observation differs in {fields}")
        if trajectory.asset_sha256 is not None:
            manifest = getattr(engine, "replay_manifest", None)
            current = manifest() if manifest is not None else None
            if current != trajectory.asset_sha256:
                changed = sorted(set(current or ()) | set(trajectory.asset_sha256))
                changed = [name for name in changed if (current or {}).get(name)
                           != trajectory.asset_sha256.get(name)]
                detail = f": {', '.join(changed[:8])}" if changed else ""
                if len(changed) > 8:
                    detail += f" (+{len(changed) - 8} more)"
                raise ReplayMismatch("native assets differ from recorded trajectory" + detail)
    return len(trajectory.decisions)
