# GOAT rules profile

Target: TCG GOAT Format with April 2005 Forbidden/Limited list and the widely used August 17, 2005 card pool. The rule profile records first-turn draw and historical Ignition priority. Full validation is pending native integration.

Sources: [GoatFormat mechanics](https://www.goatformat.com/basics.html), [card pool and banlist](https://www.goatformat.com/cardpool.html), and [ocgcore GOAT flags](https://github.com/edo9300/ygopro-core/blob/master/ocgapi_constants.h).

The M0 native probe confirms that a pinned core configured with `DUEL_MODE_GOAT` performs an opening draw for the first player in its vanilla-monster fixture. This is one startup behavior check, not a complete historical rules validation.

The M1 deck gate uses a pinned [Project Ignis GOAT whitelist](https://github.com/ProjectIgnis/LFLists/blob/master/GOAT.lflist.conf) and checks copy limits against the pinned card database. Its membership and pre-errata variants still need independent comparison with the August 17, 2005 community card pool.

Unresolved: exact script revisions for 2005 TCG card text, card-specific rulings that differ from current OCG scripts, and differences among community tournament interpretations. These require individual source-backed regression cases before a correctness claim.

