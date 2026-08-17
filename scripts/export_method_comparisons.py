#!/usr/bin/env python3
"""Export compact per-answer strategy paths from a completed Mode 3 log."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


LEVELS = ("5", "10", "11", "12")
ANSWER_HEADER = re.compile(r"^===== Answer \d+/\d+: ([a-z]{5}) =====\n", re.MULTILINE)
LEVEL_HEADER = re.compile(r"^Level (5|10|11|12) \([^\n]+\)\n", re.MULTILINE)
GUESS_LINE = re.compile(r"^Guess \d+: ([A-Z]{5}) ->", re.MULTILINE)


def parse_comparisons(log_text: str) -> dict[str, list[list[str]]]:
    chunks = ANSWER_HEADER.split(log_text)
    comparisons: dict[str, list[list[str]]] = {}
    for index in range(1, len(chunks), 2):
        answer, body = chunks[index], chunks[index + 1]
        sections = LEVEL_HEADER.split(body)
        paths: dict[str, list[str]] = {}
        for section_index in range(1, len(sections), 2):
            level, transcript = sections[section_index], sections[section_index + 1]
            paths[level] = [word.lower() for word in GUESS_LINE.findall(transcript)]

        missing = [level for level in LEVELS if level not in paths]
        if missing:
            raise ValueError(f"{answer}: missing Level {', '.join(missing)} transcript")
        for level in LEVELS:
            if not paths[level] or paths[level][-1] != answer:
                raise ValueError(f"{answer}: Level {level} path does not solve the answer")
        comparisons[answer] = [paths[level] for level in LEVELS]
    return comparisons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path, nargs="?", default=Path("mode3.log"))
    parser.add_argument(
        "output", type=Path, nargs="?", default=Path("web/data/method_comparisons.json")
    )
    args = parser.parse_args()

    comparisons = parse_comparisons(args.log.read_text())
    if not comparisons:
        raise ValueError("no completed answers found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(comparisons, separators=(",", ":")) + "\n")
    print(f"Exported {len(comparisons):,} answers to {args.output}")


if __name__ == "__main__":
    main()
