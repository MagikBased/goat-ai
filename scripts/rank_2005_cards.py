"""Rank cards appearing in the published SJC Indianapolis 2005 Top 8 lists."""

import argparse
import csv
import sys

from goat_ai.evaluation.historical_corpus import historical_card_counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be positive")
    writer = csv.writer(sys.stdout)
    writer.writerow(("lists", "copies", "card"))
    for name, lists, copies in historical_card_counts()[:args.top]:
        writer.writerow((lists, copies, name))


if __name__ == "__main__":
    main()
