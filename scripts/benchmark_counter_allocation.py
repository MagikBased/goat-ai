"""Measure a synthetic maximum-size staged counter choice, not duel throughput."""

import argparse
import hashlib
import json
import platform
import resource
import struct
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace

import torch

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.native_messages import decode_decision
from goat_ai.observations import CardView, Observation
from goat_ai.training import CardVocabulary, LegalActionPolicy, encode_decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=int, default=2)
    parser.add_argument("--available", type=int, default=32767)
    parser.add_argument("--total", type=int, default=32767)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if (not 2 <= args.cards <= 10 or not 1 <= args.available <= 32767
            or not 1 <= args.total <= min(32767, args.cards * args.available)
            or args.width < 1 or args.repeats < 1):
        parser.error("invalid counter benchmark bounds")
    torch.set_num_threads(1)
    cards = tuple((100 + index, index // 5, 4, index % 5)
                  for index in range(args.cards))
    prompt = (struct.pack("<BBHHI", 22, 0, 1, args.total, args.cards)
              + b"".join(struct.pack("<IBBBH", code, player, location,
                                      sequence, args.available)
                         for code, player, location, sequence in cards))
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(),
        field=tuple(CardView(player, "monster", "faceup", code, sequence,
                             counters=((1, args.available),))
                    for code, player, _, sequence in cards),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=0,
        deck_counts=(40, 40), extra_deck_counts=(0, 0))
    vocabulary = CardVocabulary(tuple(code for code, *_ in cards),
                                tuple((code, 17, 300) for code, *_ in cards))
    model = LegalActionPolicy(vocabulary.size, width=args.width, feature_version=28)
    model.eval()
    cpuinfo = Path("/proc/cpuinfo")
    cpu = (next((line.split(":", 1)[1].strip()
                 for line in cpuinfo.read_text().splitlines()
                 if line.startswith("model name")), platform.processor())
           if cpuinfo.is_file() else platform.processor())
    measurements = []
    for _ in range(args.repeats):
        started = perf_counter()
        native = decode_decision(prompt)
        decoded = perf_counter()
        if native.counter_selection is None:
            raise RuntimeError("benchmark prompt did not enter staged selection")
        engine = ExperimentalOcgcoreEngine(".")
        engine.probe = SimpleNamespace(
            _pending_message=prompt, decode_pending=lambda decoded=native: decoded,
            observation=lambda _player: observation)
        decision = engine._decision()
        adapted = perf_counter()
        features = encode_decision(observation, decision.legal_actions,
                                   vocabulary, feature_version=28)
        encoded = perf_counter()
        with torch.inference_mode():
            scores = model(features)
        inferred = perf_counter()
        if scores.shape != (len(decision.legal_actions),) or not torch.isfinite(scores).all():
            raise RuntimeError("policy did not score every staged amount")
        measurements.append({
            "actions": len(decision.legal_actions),
            "decode_seconds": decoded - started,
            "adapter_seconds": adapted - decoded,
            "encode_seconds": encoded - adapted,
            "inference_seconds": inferred - encoded,
        })
    print(json.dumps({
        "scenario": "synthetic_first_stage_not_a_duel",
        "platform": platform.platform(),
        "processor": cpu,
        "torch_version": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
        "cards": args.cards, "available_each": args.available,
        "counter_total": args.total, "policy_width": args.width,
        "policy_feature_version": 28,
        "repeats": args.repeats,
        "measurements": measurements,
        "median_seconds": {
            key: median(measurement[key] for measurement in measurements)
            for key in ("decode_seconds", "adapter_seconds", "encode_seconds",
                        "inference_seconds")},
        "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1024 * 1024 if platform.system() == "Darwin" else 1024),
    }, indent=2))


if __name__ == "__main__":
    main()
