#!/usr/bin/env python3
"""Convert WordGamesBot's maintained NYT JavaScript lists to plain text."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


WORD = re.compile(r'"([A-Z]{5})"')


def read_javascript_words(path: Path) -> list[str]:
    words = sorted({word.lower() for word in WORD.findall(path.read_text())})
    if not words:
        raise ValueError(f"no five-letter words found in {path}")
    return words


def write_words(path: Path, words: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(words) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers_js", type=Path, help="WordLists/NYT/Answers_with_ED.js")
    parser.add_argument("guesses_js", type=Path, help="WordLists/NYT/Words.js")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    answers = read_javascript_words(args.answers_js)
    guesses = read_javascript_words(args.guesses_js)
    missing = set(answers) - set(guesses)
    if missing:
        raise ValueError(f"{len(missing)} answers are absent from the accepted-guess list")

    answer_path = args.output_dir / "nyt_wordlebot_answers.txt"
    guess_path = args.output_dir / "nyt_accepted_guesses.txt"
    write_words(answer_path, answers)
    write_words(guess_path, guesses)
    print(f"Wrote {len(answers):,} likely answers to {answer_path}")
    print(f"Wrote {len(guesses):,} accepted guesses to {guess_path}")


if __name__ == "__main__":
    main()
