# Roadmap

1. **Working historical duel:** pin core and assets, implement decision protocol and redacted queries, validate deck legality, run random self-play through terminal states.
2. **Correctness gate:** historical timing, chain, Damage Step, flip, summon negation, and representative card-specific tests against sourced rulings.
3. **Data and evaluation:** replay reconstruction with rights checks; seed-controlled tournaments, confidence intervals, deck/matchup splits, and real throughput measurements.
4. **Learning:** PyTorch action-conditioned policy, behavioral cloning from verified player views, then self-play with opponent pools. Compare PPO and value-based approaches experimentally.
5. **Search:** benchmark belief sampling and information-set methods only after the simulator and visibility tests pass; expand to Edison with a separately validated profile.

Keep training and evaluation decks and opponents separate. Compare competitive win rates, including first/second-player splits, rather than relying on imitation accuracy.

