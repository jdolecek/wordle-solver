#!/usr/bin/env python3
"""Precompute fast second-turn rankings for the expanded mobile dictionaries."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from math import log2
from pathlib import Path


OPENING = "salet"


def feedback(guess: str, answer: str) -> tuple[int, int, int, int, int]:
    marks = [0] * 5
    remaining: Counter[str] = Counter()
    for index, (guess_letter, answer_letter) in enumerate(zip(guess, answer)):
        if guess_letter == answer_letter:
            marks[index] = 2
        else:
            remaining[answer_letter] += 1
    for index, guess_letter in enumerate(guess):
        if marks[index] == 0 and remaining[guess_letter]:
            marks[index] = 1
            remaining[guess_letter] -= 1
    return tuple(marks)  # type: ignore[return-value]


def feedback_key(result: tuple[int, int, int, int, int]) -> str:
    return "".join("BYG"[mark] for mark in result)


def heuristic_pool(candidates: list[str], guesses: list[str], limit: int = 40) -> list[str]:
    letters = Counter(letter for word in candidates for letter in set(word))
    positions = Counter((index, letter) for word in candidates for index, letter in enumerate(word))

    def score(word: str) -> float:
        unique = sum(letters[letter] for letter in set(word))
        positional = sum(positions[index, letter] for index, letter in enumerate(word))
        return unique + positional * 0.35

    return sorted(guesses, key=lambda word: (-score(word), word))[:limit]


def rank_state(candidates: list[str], guesses: list[str]) -> list[str]:
    pool = heuristic_pool(candidates, guesses)
    if len(candidates) <= 60:
        pool = list(dict.fromkeys([*pool, *candidates]))
    candidate_set = set(candidates)
    total = len(candidates)
    scored = []
    for guess in pool:
        groups = Counter(feedback(guess, answer) for answer in candidates)
        entropy = sum((size / total) * log2(total / size) for size in groups.values())
        expected = sum(size * size for size in groups.values()) / total
        scored.append(
            (-entropy, max(groups.values()), expected, guess not in candidate_set, guess)
        )
    return [row[-1] for row in sorted(scored)[:6]]


def build_states(answers: list[str], guesses: list[str]) -> dict[str, list[str]]:
    partitions: dict[str, list[str]] = defaultdict(list)
    for answer in answers:
        partitions[feedback_key(feedback(OPENING, answer))].append(answer)
    return {key: rank_state(candidates, guesses) for key, candidates in sorted(partitions.items())}


def main() -> None:
    data_dir = Path("data")
    guesses = (data_dir / "nyt_accepted_guesses.txt").read_text().split()
    dictionaries = {
        "nyt": (data_dir / "nyt_wordlebot_answers.txt").read_text().split(),
        "broad": guesses,
    }
    rankings = {name: build_states(words, guesses) for name, words in dictionaries.items()}
    output = Path("web/data/dictionary_openings.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rankings, separators=(",", ":")) + "\n")
    print(
        "Wrote "
        + ", ".join(f"{len(states)} {name} states" for name, states in rankings.items())
        + f" to {output}"
    )


if __name__ == "__main__":
    main()
