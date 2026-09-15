#!/usr/bin/env python3
"""Build deep-search trees with guesses first, leaderboard score second.

The source trees provide a strong (and, for the original list, proven) primary
guess-count policy. Large states retain exactly the same answer partitions while
choosing the partition-equivalent guess with the best buggy leaderboard reward.
Small states are searched exhaustively with the lexicographic objective:

    1. minimize total guesses across all candidate answers;
    2. maximize total cumulative tiebreak score.

Wordle feedback and leaderboard reward deliberately use different duplicate-
letter rules. See ``tiebreak_match_value`` in ``wordle_solver.core``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wordle_solver.core import (  # noqa: E402
    feedback_for,
    tiebreak_match_value,
    tiebreak_score,
)

GREEN = (2, 2, 2, 2, 2)
GREEN_CODE = 242
INFINITY = 10**9


def feedback_key(guess: str, answer: str) -> str:
    return "".join("BYG"[mark] for mark in feedback_for(guess, answer))


def feedback_code(guess: str, answer: str) -> int:
    result = feedback_for(guess, answer)
    return sum(mark * 3**index for index, mark in enumerate(result))


def parse_policy(path: Path) -> dict[tuple[str, ...], str]:
    """Parse Alex Selby's fixed-width decision-tree format."""
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
                key = tuple(feedbacks[:depth])
                existing = policy.setdefault(key, guesses[depth])
                if existing != guesses[depth]:
                    raise ValueError(f"conflicting policy choices at {key}")
    return policy


@dataclass(frozen=True)
class SearchResult:
    guesses: int
    tiebreak: int
    word: str


class Baseline:
    """Candidate states and remaining costs represented by an existing tree."""

    def __init__(self, answers: list[str], policy: dict[tuple[str, ...], str]):
        self.answers = tuple(sorted(answers))
        self.policy = policy
        states: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)
        costs: Counter[tuple[str, ...]] = Counter()

        for answer in self.answers:
            history: list[str] = []
            path: list[tuple[str, ...]] = []
            for _turn in range(1, 7):
                key = tuple(history)
                path.append(key)
                guess = policy[key]
                if guess == answer:
                    break
                history.append(feedback_key(guess, answer))
            else:
                raise RuntimeError(f"baseline did not solve {answer.upper()} within six guesses")

            for index, key in enumerate(path):
                states[key].append(answer)
                costs[key] += len(path) - index

        self.candidates_by_history = {
            history: tuple(sorted(candidates)) for history, candidates in states.items()
        }
        self.history_by_candidates: dict[tuple[str, ...], tuple[str, ...]] = {}
        for history, candidates in self.candidates_by_history.items():
            if candidates in self.history_by_candidates:
                raise ValueError("baseline reaches the same candidate set by two paths")
            self.history_by_candidates[candidates] = history
        self.cost_by_candidates = {
            self.candidates_by_history[history]: cost for history, cost in costs.items()
        }

    def word_for(self, candidates: tuple[str, ...]) -> str:
        return self.policy[self.history_by_candidates[candidates]]


class TiebreakBuilder:
    def __init__(
        self,
        baseline: Baseline,
        allowed_guesses: list[str],
        exact_threshold: int,
    ):
        self.baseline = baseline
        baseline_words = set(baseline.policy.values())
        allowed = set(allowed_guesses)
        missing = baseline_words - allowed
        if missing:
            sample = ", ".join(sorted(missing)[:5])
            raise ValueError(f"baseline uses guesses absent from the accepted list: {sample}")
        self.allowed_guesses = tuple(sorted(allowed))
        self.exact_threshold = exact_threshold
        self.equivalent_changes = 0
        self.exact_states = 0

    @lru_cache(maxsize=None)
    def exact(self, candidates: tuple[str, ...], depth: int) -> SearchResult:
        """Exhaustively solve a small state using an integer tuple objective."""
        self.exact_states += 1
        size = len(candidates)
        multiplier = 6 - depth
        if size == 1:
            answer = candidates[0]
            return SearchResult(1, multiplier * 10, answer)
        if depth >= 5:
            return SearchResult(INFINITY, -INFINITY, "")

        # Exact feedback signatures have identical child states. Retain only the
        # representative with the greatest immediate tiebreak reward.
        representatives: dict[bytes, tuple[int, str]] = {}
        for guess in self.allowed_guesses:
            signature = bytes(feedback_code(guess, answer) for answer in candidates)
            if len(set(signature)) == 1 and signature[0] != GREEN_CODE:
                continue
            immediate = sum(tiebreak_match_value(guess, answer) for answer in candidates)
            previous = representatives.get(signature)
            if previous is None or immediate > previous[0] or (
                immediate == previous[0] and guess < previous[1]
            ):
                representatives[signature] = (immediate, guess)

        baseline_bound = self.baseline.cost_by_candidates.get(candidates, INFINITY)
        rows: list[tuple[int, int, str, int, tuple[tuple[str, ...], ...]]] = []
        for signature, (immediate, guess) in representatives.items():
            groups: defaultdict[int, list[str]] = defaultdict(list)
            for answer, code in zip(candidates, signature):
                if code != GREEN_CODE:
                    groups[code].append(answer)
            children = tuple(tuple(sorted(group)) for group in groups.values())
            lower_bound = size + sum(2 * len(child) - 1 for child in children)
            if lower_bound <= baseline_bound:
                rows.append((lower_bound, -immediate, guess, immediate, children))
        rows.sort()

        best_guesses = baseline_bound
        best_tiebreak = -INFINITY
        best_word = ""
        for lower_bound, _negative_immediate, guess, immediate, children in rows:
            if lower_bound > best_guesses:
                break
            total_guesses = size
            total_tiebreak = multiplier * immediate
            for child in children:
                result = self.exact(child, depth + 1)
                total_guesses += result.guesses
                total_tiebreak += result.tiebreak
                if total_guesses > best_guesses:
                    break
            if total_guesses < best_guesses or (
                total_guesses == best_guesses and total_tiebreak > best_tiebreak
            ):
                best_guesses = total_guesses
                best_tiebreak = total_tiebreak
                best_word = guess

        if not best_word:
            raise RuntimeError(
                f"no feasible choice for {len(candidates)} answers at turn {depth + 1}"
            )
        return SearchResult(best_guesses, best_tiebreak, best_word)

    @lru_cache(maxsize=None)
    def equivalent_word(self, candidates: tuple[str, ...]) -> str:
        """Maximize reward among guesses inducing the baseline partition."""
        baseline_word = self.baseline.word_for(candidates)
        group_numbers: dict[int, int] = {}
        baseline_groups: list[int] = []
        for answer in candidates:
            code = feedback_code(baseline_word, answer)
            group_numbers.setdefault(code, len(group_numbers))
            baseline_groups.append(group_numbers[code])

        best_reward = sum(
            tiebreak_match_value(baseline_word, answer) for answer in candidates
        )
        best_word = baseline_word
        baseline_can_solve = baseline_word in candidates
        for guess in self.allowed_guesses:
            # Partition isomorphism alone is insufficient when one word can be
            # the answer and the other cannot: that changes whether one branch
            # terminates on this turn. Requiring equal solve eligibility keeps
            # the aggregate primary cost exactly unchanged.
            if (guess in candidates) != baseline_can_solve:
                continue
            baseline_to_guess: dict[int, int] = {}
            guess_to_baseline: dict[int, int] = {}
            for answer, baseline_group in zip(candidates, baseline_groups):
                code = feedback_code(guess, answer)
                if (
                    baseline_group in baseline_to_guess
                    and baseline_to_guess[baseline_group] != code
                ) or (code in guess_to_baseline and guess_to_baseline[code] != baseline_group):
                    break
                baseline_to_guess[baseline_group] = code
                guess_to_baseline[code] = baseline_group
            else:
                reward = sum(
                    tiebreak_match_value(guess, answer) for answer in candidates
                )
                if reward > best_reward:
                    best_reward = reward
                    best_word = guess

        if best_word != baseline_word:
            self.equivalent_changes += 1
        return best_word

    def choice(self, candidates: tuple[str, ...], depth: int) -> str:
        if depth == 0:
            return self.baseline.word_for(candidates)
        if len(candidates) <= self.exact_threshold:
            return self.exact(candidates, depth).word
        return self.equivalent_word(candidates)

    def paths(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for answer in self.baseline.answers:
            candidates = self.baseline.answers
            path: list[str] = []
            for depth in range(6):
                guess = self.choice(candidates, depth)
                path.append(guess)
                if guess == answer:
                    break
                observed = feedback_for(guess, answer)
                candidates = tuple(
                    candidate
                    for candidate in candidates
                    if feedback_for(guess, candidate) == observed
                )
            else:
                raise RuntimeError(
                    f"new strategy did not solve {answer.upper()} within six guesses"
                )
            result[answer] = path
        return result


def write_full_tree(paths: dict[str, list[str]], output: Path) -> None:
    lines = []
    for answer, guesses in sorted(paths.items()):
        segments = []
        for turn, guess in enumerate(guesses, start=1):
            segments.append(f"{guess:<5} {feedback_key(guess, answer)}{turn} ")
        lines.append("".join(segments).rstrip())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def metrics(paths: dict[str, list[str]]) -> dict[str, object]:
    counts = Counter(len(path) for path in paths.values())
    total_guesses = sum(turns * count for turns, count in counts.items())
    total_tiebreak = sum(tiebreak_score(path, answer) for answer, path in paths.items())
    return {
        "answers": len(paths),
        "totalGuesses": total_guesses,
        "averageGuesses": total_guesses / len(paths),
        "totalTiebreak": total_tiebreak,
        "averageTiebreak": total_tiebreak / len(paths),
        "min": min(counts),
        "max": max(counts),
        "counts": [counts[turn] for turn in range(min(counts), max(counts) + 1)],
    }


def baseline_paths(baseline: Baseline) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}
    for answer in baseline.answers:
        history: list[str] = []
        path: list[str] = []
        for _turn in range(6):
            guess = baseline.policy[tuple(history)]
            path.append(guess)
            if guess == answer:
                break
            history.append(feedback_key(guess, answer))
        paths[answer] = path
    return paths


def build_profile(
    name: str,
    answers_path: Path,
    baseline_path: Path,
    output_path: Path,
    allowed_guesses: list[str],
    exact_threshold: int,
) -> tuple[dict[str, list[str]], dict[str, object]]:
    answers = answers_path.read_text().split()
    baseline = Baseline(answers, parse_policy(baseline_path))
    old_metrics = metrics(baseline_paths(baseline))
    builder = TiebreakBuilder(baseline, allowed_guesses, exact_threshold)
    paths = builder.paths()
    new_metrics = metrics(paths)
    if new_metrics["totalGuesses"] > old_metrics["totalGuesses"]:
        raise RuntimeError(f"{name}: primary guess count became worse")
    if (
        new_metrics["totalGuesses"] == old_metrics["totalGuesses"]
        and new_metrics["totalTiebreak"] < old_metrics["totalTiebreak"]
    ):
        raise RuntimeError(f"{name}: equal-speed tiebreak score became worse")
    write_full_tree(paths, output_path)
    print(
        f"{name}: {old_metrics['averageGuesses']:.5f} → "
        f"{new_metrics['averageGuesses']:.5f} guesses; "
        f"{old_metrics['averageTiebreak']:.5f} → "
        f"{new_metrics['averageTiebreak']:.5f} tiebreak "
        f"({builder.equivalent_changes} large-state changes, "
        f"{builder.exact_states} exact states)"
    )
    return paths, new_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exact-threshold",
        type=int,
        default=10,
        help="exhaustively optimize states at or below this candidate count (default: 10)",
    )
    args = parser.parse_args()
    data = ROOT / "data"
    web_data = ROOT / "web" / "data"
    allowed = (data / "nyt_accepted_guesses.txt").read_text().split()

    original_paths, original_metrics = build_profile(
        "original",
        data / "solutions.txt",
        data / "optimal_strategy.txt",
        data / "tiebreak_strategy.txt",
        allowed,
        args.exact_threshold,
    )
    editor_paths, editor_metrics = build_profile(
        "editor",
        data / "nyt_editor_answers.txt",
        data / "editor_strategy.txt",
        data / "editor_tiebreak_strategy.txt",
        allowed,
        args.exact_threshold,
    )

    web_data.mkdir(parents=True, exist_ok=True)
    (web_data / "tiebreak_strategy.txt").write_text(
        (data / "tiebreak_strategy.txt").read_text()
    )
    (web_data / "editor_tiebreak_strategy.txt").write_text(
        (data / "editor_tiebreak_strategy.txt").read_text()
    )
    (web_data / "tiebreak_comparisons.json").write_text(
        json.dumps(original_paths, separators=(",", ":")) + "\n"
    )
    (web_data / "tiebreak_stats.json").write_text(
        json.dumps(
            {"original": original_metrics, "editor": editor_metrics},
            separators=(",", ":"),
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
