#!/usr/bin/env python3
"""Verify the bundled editor-aware decision tree and print its distribution."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wordle_solver.core import feedback_for  # noqa: E402


def parse_policy(path: Path) -> dict[tuple[str, ...], str]:
    policy: dict[tuple[str, ...], str] = {}
    guesses: list[str] = []
    feedbacks: list[str] = []
    for line in path.read_text().splitlines():
        for depth in range((len(line) + 12) // 13):
            segment = line[depth * 13 : (depth + 1) * 13].ljust(13)
            word = segment[:5].strip().lower()
            feedback = segment[6:11]
            if word:
                guesses[depth:] = [word]
                feedbacks[depth:] = []
            if feedback.strip():
                feedbacks[depth:] = [feedback]
                policy.setdefault(tuple(feedbacks[:depth]), guesses[depth])
    return policy


def feedback_key(guess: str, answer: str) -> str:
    return "".join("BYG"[mark] for mark in feedback_for(guess, answer))


def score(policy: dict[tuple[str, ...], str], answer: str) -> int:
    history: list[str] = []
    for turn in range(1, 7):
        guess = policy[tuple(history)]
        if guess == answer:
            return turn
        history.append(feedback_key(guess, answer))
    raise RuntimeError(f"strategy did not solve {answer.upper()} within six guesses")


def main() -> None:
    candidates = (ROOT / "data" / "nyt_editor_answers.txt").read_text().split()
    policy = parse_policy(ROOT / "data" / "editor_strategy.txt")
    scores = [score(policy, answer) for answer in candidates]
    total = sum(scores)
    if len(candidates) != 1_319 or total != 4_303:
        raise RuntimeError(f"unexpected strategy result: {len(candidates)} answers, {total} guesses")
    distribution = Counter(scores)
    print(f"Verified {len(candidates):,} answers in {total:,} guesses ({total / len(candidates):.5f} average)")
    print("Distribution: " + ", ".join(f"{turn}: {distribution[turn]:,}" for turn in sorted(distribution)))


if __name__ == "__main__":
    main()
