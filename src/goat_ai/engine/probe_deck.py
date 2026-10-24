"""40-card normal-monster fixture for the core startup probe.

Card-pool and historical print validation are M1 work. The fixture tests the
native first-draw path, not competitive deck legality or card effect handling.
"""

# Thirteen different normal monsters at three copies each, plus one Inpachi.
VANILLA_DECK: tuple[int, ...] = (
    15025844, 13039848, 5053103, 97590747, 23771716,
    51934376, 69140098, 7359741, 49881766, 79182538,
    62651957, 11321183, 49003308,
) * 3 + (97923414,)
