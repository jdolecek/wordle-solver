#!/usr/bin/env python3
"""Verify the bundled leaderboard-optimized decision trees."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wordle_solver.core import tiebreak_score  # noqa: E402

from build_tiebreak_strategies import feedback_key, metrics, parse_policy  # noqa: E402


def verify(
    name: str,
    answers_path: Path,
    tree_path: Path,
    expected_guesses: int,
    expected_tiebreak: int,
) -> dict[str, list[str]]:
    answers = answers_path.read_text().split()
    policy = parse_policy(tree_path)
    paths: dict[str, list[str]] = {}
    for answer in answers:
        history: list[str] = []
        path: list[str] = []
        for _turn in range(6):
            guess = policy[tuple(history)]
            path.append(guess)
            if guess == answer:
                break
            history.append(feedback_key(guess, answer))
        else:
            raise RuntimeError(f"{name} did not solve {answer.upper()} within six guesses")
        paths[answer] = path

    total_guesses = sum(len(path) for path in paths.values())
    total_tiebreak = sum(tiebreak_score(path, answer) for answer, path in paths.items())
    if (total_guesses, total_tiebreak) != (expected_guesses, expected_tiebreak):
        raise RuntimeError(
            f"{name}: expected {(expected_guesses, expected_tiebreak)}, "
            f"got {(total_guesses, total_tiebreak)}"
        )
    print(
        f"Verified {name}: {len(answers):,} answers, "
        f"{total_guesses / len(answers):.5f} guesses, "
        f"{total_tiebreak / len(answers):.5f} tiebreak, "
        f"max {max(map(len, paths.values()))} guesses"
    )
    return paths


def main() -> None:
    data = ROOT / "data"
    original_paths = verify(
        "original leaderboard tree",
        data / "solutions.txt",
        data / "tiebreak_strategy.txt",
        7_918,
        174_682,
    )
    editor_paths = verify(
        "editor-aware leaderboard tree",
        data / "nyt_editor_answers.txt",
        data / "editor_tiebreak_strategy.txt",
        4_303,
        96_091,
    )
    if (data / "tiebreak_strategy.txt").read_bytes() != (
        ROOT / "web" / "data" / "tiebreak_strategy.txt"
    ).read_bytes():
        raise RuntimeError("original web strategy copy is stale")
    if (data / "editor_tiebreak_strategy.txt").read_bytes() != (
        ROOT / "web" / "data" / "editor_tiebreak_strategy.txt"
    ).read_bytes():
        raise RuntimeError("editor web strategy copy is stale")

    web_data = ROOT / "web" / "data"
    comparison_paths = json.loads((web_data / "tiebreak_comparisons.json").read_text())
    if comparison_paths != original_paths:
        raise RuntimeError("web tiebreak comparison paths are stale")
    published_stats = json.loads((web_data / "tiebreak_stats.json").read_text())
    expected_stats = {
        "original": metrics(original_paths),
        "editor": metrics(editor_paths),
    }
    if published_stats != expected_stats:
        raise RuntimeError("web tiebreak statistics are stale")

    accepted = set((data / "nyt_accepted_guesses.txt").read_text().split())
    policy_words = set()
    for paths in (original_paths, editor_paths):
        for path in paths.values():
            policy_words.update(path)
    missing = policy_words - accepted
    if missing:
        raise RuntimeError(f"strategy uses unaccepted guesses: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    main()
