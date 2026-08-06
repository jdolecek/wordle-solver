from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
from functools import lru_cache
from math import log2
from pathlib import Path

from .core import Feedback, WordleSolver, feedback_for


def main() -> None:
    parser = argparse.ArgumentParser(description="Explainable information-theoretic Wordle solver")
    parser.add_argument("--answers", type=Path, help="Optional file containing one possible answer per line")
    parser.add_argument("--guesses", type=Path, help="Optional file containing one allowed guess per line")
    args = parser.parse_args()

    answers, guesses = load_words(args.answers, args.guesses)
    mode = choose_mode()

    if mode == "known":
        solve_known_answers(answers, guesses)
    elif mode == "benchmark":
        benchmark_all_answers(answers, guesses)
    else:
        solver = WordleSolver(answers, guesses, aggressiveness=5)
        history = collect_existing_history(solver) if mode == "resume" else None
        if optimal_strategy_available(answers) and optimal_history_supported(history or []):
            run_optimal_interactive(solver, history)
        else:
            if history:
                print("\nThat history is outside Level 12's fixed tree; continuing with Level 5.")
            run_interactive(solver, history)


def choose_mode() -> str:
    print("\nWordle solver")
    print("1. Play with the solver")
    print("2. Solve a known answer and calculate the score")
    print("3. Benchmark all loaded Wordle solutions")
    print("4. Resume a puzzle already in progress")
    while True:
        choice = input("Choose a mode (1/2/3/4): ").strip().lower()
        if choice in {"1", "play", "interactive"}:
            return "interactive"
        if choice in {"2", "solve", "known"}:
            return "known"
        if choice in {"3", "benchmark", "all"}:
            return "benchmark"
        if choice in {"4", "resume", "existing"}:
            return "resume"
        print("Please choose 1, 2, 3, or 4.")


def benchmark_all_answers(answers: list[str], guesses: list[str]) -> None:
    """Run every strategy against every loaded answer without interactive input."""
    strategy_names = [
        "Level 5 greedy",
        "Level 10 minimax (Wordle guesses)",
        "Level 11 expected turns (Wordle guesses)",
    ]
    if optimal_strategy_available(answers):
        strategy_names.append("Level 12 provably optimal")
    totals = [0] * len(strategy_names)
    solved = [0] * len(strategy_names)
    log_path = Path("mode3.log")
    print(f"\nBenchmarking {len(answers)} loaded solutions across {len(strategy_names)} strategies...")
    print(f"Complete transcript: {log_path.resolve()}")
    # Answers that produce the same feedback share the same candidate state.
    # Cache rankings by that state so the benchmark builds each strategy's
    # decision tree once instead of rediscovering it for every answer.
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] = {}

    with log_path.open("w") as log:
        log.write(f"Mode 3 benchmark: {len(answers)} answers, {len(strategy_names)} strategies\n\n")
        for index, answer in enumerate(answers, start=1):
            scores, transcript = _scores_for_answer(
                answers, guesses, answer, capture=True, choice_cache=choice_cache
            )
            log.write(f"===== Answer {index}/{len(answers)}: {answer} =====\n")
            log.write(transcript)
            log.write("Scores: " + ", ".join(str(score) for score in scores) + "\n\n")
            for strategy_index, score in enumerate(scores):
                totals[strategy_index] += score
                solved[strategy_index] += score <= 6
            if index == 1 or index % 100 == 0 or index == len(answers):
                progress = f"  Processed {index}/{len(answers)}"
                print(progress)
                log.write(progress + "\n")

    results = []
    for index, name in enumerate(strategy_names):
        results.append((totals[index] / len(answers), name, solved[index]))
    results.sort()
    print("\nMode 3 summary")
    for average, name, solved_count in results:
        print(f"  {name}: average {average:.2f}/6, solved in 6 or fewer {solved_count}/{len(answers)}")
    print(f"  Best overall strategy: {results[0][1]} ({results[0][0]:.2f}/6 average)")
    with log_path.open("a") as log:
        log.write("\nMode 3 summary\n")
        for average, name, solved_count in results:
            log.write(
                f"  {name}: average {average:.2f}/6, "
                f"solved in 6 or fewer {solved_count}/{len(answers)}\n"
            )
        log.write(f"  Best overall strategy: {results[0][1]} ({results[0][0]:.2f}/6 average)\n")


def _scores_for_answer(
    answers: list[str],
    guesses: list[str],
    answer: str,
    capture: bool = False,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> tuple[list[int], str] | list[int]:
    """Reuse the mode-2 strategies while suppressing their per-guess output."""
    scores: list[int] = []
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        solver = WordleSolver(answers, guesses, aggressiveness=5)
        scores.append(solve_known_level(solver, answer, 5, choice_cache))
        scores.append(solve_minimax_level(answers, guesses, answer, choice_cache))
        scores.append(solve_expected_turns_level(answers, guesses, answer, choice_cache))
        if optimal_strategy_available(answers):
            scores.append(solve_optimal_level(answer))
    if capture:
        return scores, output.getvalue()
    return scores


def collect_existing_history(solver: WordleSolver) -> list[tuple[str, Feedback]]:
    """Collect guesses already played, rejecting contradictory feedback."""
    history: list[tuple[str, Feedback]] = []
    print("\nEnter each guess you already played and its feedback.")
    print("Use g/y/b for green/yellow/gray. Press Enter at the guess prompt when done.")
    while True:
        guess = input("Previous guess (or Enter to continue): ").strip().lower()
        if not guess:
            return history
        if len(guess) != 5 or not guess.isalpha():
            print("Input error: guess must be exactly five letters.", file=sys.stderr)
            continue

        result_text = input(f"Result for {guess.upper()} (g/y/b): ").strip().lower()
        try:
            result = parse_feedback(result_text)
        except ValueError as error:
            print(f"Input error: {error}", file=sys.stderr)
            continue

        proposed = [*history, (guess, result)]
        candidates = solver.narrow(proposed)
        if not candidates and result != (2, 2, 2, 2, 2):
            print(
                "That feedback conflicts with the earlier entries; the guess was not added.",
                file=sys.stderr,
            )
            continue
        history = proposed
        print(f"  {len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain.")
        if result == (2, 2, 2, 2, 2):
            return history


def run_interactive(
    solver: WordleSolver, history: list[tuple[str, Feedback]] | None = None
) -> None:
    history = list(history or [])
    if history and history[-1][1] == (2, 2, 2, 2, 2):
        print(f"\nPuzzle already solved with {history[-1][0].upper()}.")
        return

    opening_guess = solver.rank_guesses(solver.answers, limit=1)[0].word
    print("Wordle solver. Enter feedback as g/y/b (green/yellow/gray). Type quit to exit.")
    if not history:
        print(f"Opening guess: {opening_guess.upper()}")
    else:
        print(f"Continuing after {len(history)} previous guess{'es' if len(history) != 1 else ''}.")
    while True:
        candidates = solver.narrow(history)
        print(f"\n{len(candidates)} possible answers remain.")
        if not candidates:
            print("No candidates remain. Check the spelling and feedback history.")
        else:
            print("Top potential matches:")
            print("  " + ", ".join(solver.top_matches(candidates)))
            print("Best information guesses:")
            for score in solver.rank_guesses(candidates):
                print(
                    f"  {score.word}: {score.entropy:.2f} bits, "
                    f"about {score.expected_remaining:.1f} remain, "
                    f"worst case {score.worst_case}"
                )

        guess = solver.rank_guesses(candidates, limit=1)[0].word if candidates else ""
        if not history:
            guess = opening_guess
        result_text = input(f"\nEnter result for {guess.upper()} (g/y/b), or quit: ").strip().lower()
        if result_text in {"quit", "q", "exit"}:
            return
        try:
            result = parse_feedback(result_text)
            history.append((guess, result))
        except ValueError as error:
            print(f"Input error: {error}", file=sys.stderr)


def optimal_history_supported(history: list[tuple[str, Feedback]]) -> bool:
    """Return whether prior guesses follow the exact optimal policy."""
    policy, _ = load_optimal_policy()
    feedback_history: list[str] = []
    for guess, result in history:
        expected = policy.get(tuple(feedback_history))
        if guess != expected:
            return False
        feedback_history.append(format_feedback(result).upper())
    return tuple(feedback_history) in policy or bool(history and history[-1][1] == (2, 2, 2, 2, 2))


def run_optimal_interactive(
    solver: WordleSolver, history: list[tuple[str, Feedback]] | None = None
) -> None:
    """Play or resume along the globally optimal decision tree."""
    history = list(history or [])
    policy, _ = load_optimal_policy()
    print("Wordle solver: Level 12 provably optimal strategy.")
    while True:
        candidates = solver.narrow(history)
        if history and history[-1][1] == (2, 2, 2, 2, 2):
            print(f"Puzzle solved with {history[-1][0].upper()}.")
            return
        feedback_history = tuple(format_feedback(result).upper() for _, result in history)
        guess = policy[feedback_history]
        print(f"\n{len(candidates)} possible answers remain.")
        print("Top potential matches:")
        print("  " + ", ".join(solver.top_matches(candidates)))
        print(f"Optimal next guess: {guess.upper()}")
        result_text = input(f"Enter result for {guess.upper()} (g/y/b), or quit: ").strip().lower()
        if result_text in {"quit", "q", "exit"}:
            return
        try:
            result = parse_feedback(result_text)
            proposed = [*history, (guess, result)]
            if not solver.narrow(proposed):
                print("Input error: that feedback leaves no possible answers.", file=sys.stderr)
                continue
            history = proposed
        except ValueError as error:
            print(f"Input error: {error}", file=sys.stderr)


def solve_known_answers(answers: list[str], guesses: list[str]) -> None:
    while True:
        answer = input("Enter the five-letter answer to solve: ").strip().lower()
        if answer in answers:
            break
        print("That word is not in the current answer dictionary. Try again.", file=sys.stderr)

    print(f"\nSolving {answer.upper()} with all retained strategies")
    solver = WordleSolver(answers, guesses, aggressiveness=5)
    greedy_score = solve_known_level(solver, answer, 5)

    minimax_score = solve_minimax_level(answers, guesses, answer)
    expected_turns_score = solve_expected_turns_level(answers, guesses, answer)
    optimal_score = solve_optimal_level(answer) if optimal_strategy_available(answers) else None

    print("\nSummary")
    print(f"  Level 5 Greedy: {greedy_score}/6")
    print(f"  Level 10 Minimax (Wordle guesses): {minimax_score}/6")
    print(f"  Level 11 Expected turns (Wordle guesses): {expected_turns_score}/6")
    if optimal_score is not None:
        print(f"  Level 12 Provably optimal: {optimal_score}/6")


def solve_known_level(
    solver: WordleSolver,
    answer: str,
    aggressiveness: int,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> int:
    candidates = solver.answers
    path: list[tuple[str, Feedback, int]] = []
    attempted: set[str] = set()
    opening_guess = _ranked_words(solver, candidates, aggressiveness, choice_cache)[0]
    guess = opening_guess

    print(f"\nLevel {aggressiveness} ({_aggressiveness_label(aggressiveness)})")
    while True:
        result = feedback_for(guess, answer)
        candidates = [word for word in candidates if feedback_for(guess, word) == result]
        path.append((guess, result, len(candidates)))
        attempted.add(guess)
        print(
            f"Guess {len(path)}: {guess.upper()} -> {format_feedback(result)} "
            f"({len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain)"
        )

        if guess == answer:
            break
        if len(candidates) == 1:
            guess = candidates[0]
        else:
            ranked = _ranked_words(solver, candidates, aggressiveness, choice_cache)
            guess = next((word for word in ranked if word not in attempted), answer)

    score = len(path)
    print(f"Score: {score}/6")
    return score


def solve_random_level(
    answers: list[str], guesses: list[str], answer: str, level: int = 6,
    strict_guesses: bool = False,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> int:
    """Solve with the optimal level-5 opener and a random level thereafter."""
    solver = WordleSolver(
        answers, guesses, aggressiveness=5, include_answers_in_guesses=not strict_guesses
    )
    candidates = solver.answers
    attempted: set[str] = set()
    path: list[tuple[str, Feedback, int]] = []
    guess = _ranked_words(solver, candidates, 5, choice_cache)[0]

    label = "random, optimal opening" if level == 6 else "random (Wordle guesses), optimal opening"
    print(f"\nLevel {level} ({label})")
    while True:
        result = feedback_for(guess, answer)
        candidates = [word for word in candidates if feedback_for(guess, word) == result]
        path.append((guess, result, len(candidates)))
        attempted.add(guess)
        print(
            f"Guess {len(path)}: {guess.upper()} -> {format_feedback(result)} "
            f"({len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain)"
        )

        if guess == answer:
            break
        if len(candidates) == 1:
            guess = candidates[0]
            continue

        random_level = random.randint(1, 5)
        random_solver = WordleSolver(
            answers,
            guesses,
            aggressiveness=random_level,
            include_answers_in_guesses=not strict_guesses,
        )
        ranked = _ranked_words(random_solver, candidates, random_level, choice_cache)
        guess = next((word for word in ranked if word not in attempted), answer)
        print(f"  Next aggressiveness: {random_level}")

    score = len(path)
    print(f"Level {level} score: {score}/6")
    return score


def solve_adaptive_level(
    answers: list[str], guesses: list[str], answer: str, level: int = 7,
    strict_guesses: bool = False,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> int:
    """Use historical answer frequency first, then adapt between two methods."""
    frequency_solver = WordleSolver(
        answers, guesses, aggressiveness=1, include_answers_in_guesses=not strict_guesses
    )
    entropy_solver = WordleSolver(
        answers, guesses, aggressiveness=5, include_answers_in_guesses=not strict_guesses
    )
    candidates = frequency_solver.answers
    attempted: set[str] = set()
    path: list[str] = []

    # The first guess is the most frequent historical solution word, not an
    # information probe that may never have been a real daily answer.
    if strict_guesses:
        guess = max(frequency_solver.guesses, key=lambda word: (frequency_solver._frequency[word], word))
    else:
        guess = frequency_solver.top_matches(candidates, limit=1)[0]
    label = "adaptive, historical-frequency opening"
    if strict_guesses:
        label = "adaptive (Wordle guesses), historical-frequency opening"
    print(f"\nLevel {level} ({label})")

    while True:
        result = feedback_for(guess, answer)
        candidates = [word for word in candidates if feedback_for(guess, word) == result]
        attempted.add(guess)
        path.append(guess)
        print(
            f"Guess {len(path)}: {guess.upper()} -> {format_feedback(result)} "
            f"({len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain)"
        )

        if guess == answer:
            break
        if len(candidates) == 1:
            guess = candidates[0]
            continue

        frequency_guess = _next_untried(
            frequency_solver, candidates, attempted, aggressiveness=1, choice_cache=choice_cache
        )
        entropy_guess = _next_untried(
            entropy_solver, candidates, attempted, aggressiveness=5, choice_cache=choice_cache
        )
        frequency_remaining = _remaining_after_guess(frequency_guess, candidates, answer)
        entropy_remaining = _remaining_after_guess(entropy_guess, candidates, answer)

        if frequency_remaining <= entropy_remaining:
            guess = frequency_guess
            method = "frequency"
        else:
            guess = entropy_guess
            method = "entropy"
        print(f"  Next method: {method} ({frequency_remaining} vs {entropy_remaining} candidates)")

    score = len(path)
    print(f"Level {level} score: {score}/6")
    return score


def solve_minimax_level(
    answers: list[str], guesses: list[str], answer: str,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> int:
    """Use Wordle guesses, minimizing the worst-case remaining answer set."""
    solver = WordleSolver(answers, guesses, aggressiveness=5, include_answers_in_guesses=False)
    candidates = solver.answers
    attempted: set[str] = set()
    path: list[str] = []
    print("\nLevel 10 (minimax, Wordle guesses)")

    while True:
        if len(candidates) == 1:
            guess = candidates[0]
        else:
            key = ("minimax", tuple(solver.guesses), tuple(candidates), tuple(sorted(attempted)))
            cached = choice_cache.get(key) if choice_cache is not None else None
            if cached is None:
                cached = (_best_minimax_guess(solver, candidates, attempted),)
                if choice_cache is not None:
                    choice_cache[key] = cached
            guess = cached[0]
        result = feedback_for(guess, answer)
        candidates = [word for word in candidates if feedback_for(guess, word) == result]
        attempted.add(guess)
        path.append(guess)
        print(
            f"Guess {len(path)}: {guess.upper()} -> {format_feedback(result)} "
            f"({len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain)"
        )
        if guess == answer:
            break

    score = len(path)
    print(f"Level 10 score: {score}/6")
    return score


def solve_expected_turns_level(
    answers: list[str], guesses: list[str], answer: str,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> int:
    """Minimize expected candidates left, treating an immediate solve as zero work."""
    solver = WordleSolver(answers, guesses, aggressiveness=5, include_answers_in_guesses=False)
    candidates = solver.answers
    attempted: set[str] = set()
    path: list[str] = []
    print("\nLevel 11 (expected turns, Wordle guesses)")

    while True:
        if len(candidates) == 1:
            guess = candidates[0]
        else:
            key = ("expected", tuple(solver.guesses), tuple(candidates), tuple(sorted(attempted)))
            cached = choice_cache.get(key) if choice_cache is not None else None
            if cached is None:
                cached = (_best_expected_turns_guess(solver, candidates, attempted),)
                if choice_cache is not None:
                    choice_cache[key] = cached
            guess = cached[0]
        result = feedback_for(guess, answer)
        candidates = [word for word in candidates if feedback_for(guess, word) == result]
        attempted.add(guess)
        path.append(guess)
        print(
            f"Guess {len(path)}: {guess.upper()} -> {format_feedback(result)} "
            f"({len(candidates)} possible answer{'s' if len(candidates) != 1 else ''} remain)"
        )
        if guess == answer:
            break

    score = len(path)
    print(f"Level 11 score: {score}/6")
    return score


def solve_optimal_level(answer: str) -> int:
    """Follow the published globally optimal normal-mode decision tree."""
    policy, _ = load_optimal_policy()
    feedback_history: list[str] = []
    print("\nLevel 12 (provably optimal decision tree)")
    for turn in range(1, 6):
        guess = policy[tuple(feedback_history)]
        result = feedback_for(guess, answer)
        feedback_text = format_feedback(result).upper()
        feedback_history.append(feedback_text)
        print(f"Guess {turn}: {guess.upper()} -> {feedback_text.lower()}")
        if guess == answer:
            print(f"Level 12 score: {turn}/6")
            return turn
    raise RuntimeError(f"optimal strategy did not solve {answer}")


def optimal_strategy_available(answers: list[str]) -> bool:
    """Return whether the bundled exact policy matches this answer set."""
    _, policy_answers = load_optimal_policy()
    return set(answers) == policy_answers


@lru_cache(maxsize=1)
def load_optimal_policy() -> tuple[dict[tuple[str, ...], str], set[str]]:
    """Parse Alex Selby's fixed-width optimal decision-tree format."""
    path = Path(__file__).resolve().parents[2] / "data" / "optimal_strategy.txt"
    policy: dict[tuple[str, ...], str] = {}
    answers: set[str] = set()
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
                    raise ValueError("conflicting guesses in optimal strategy")
                if feedback == "GGGGG":
                    answers.add(guesses[depth])

    return policy, answers


def _best_expected_turns_guess(
    solver: WordleSolver, candidates: list[str], attempted: set[str]
) -> str:
    """Choose the guess with least expected remaining work after this turn.

    Unlike ordinary expected partition size, the all-green partition contributes
    zero: guessing the answer finishes the game rather than leaving one candidate.
    """
    solved = (2, 2, 2, 2, 2)
    candidate_set = set(candidates)
    scored: list[tuple[float, int, float, bool, float, str]] = []
    for guess in solver._guess_pool(candidates):
        if guess in attempted:
            continue
        partitions: dict[Feedback, int] = {}
        for candidate in candidates:
            result = feedback_for(guess, candidate)
            partitions[result] = partitions.get(result, 0) + 1
        total = len(candidates)
        expected_work = sum(
            size * size for result, size in partitions.items() if result != solved
        ) / total
        scored.append(
            (
                expected_work,
                max(partitions.values()),
                sum(size * size for size in partitions.values()) / total,
                guess not in candidate_set,
                -solver._frequency.get(guess, 0.0),
                guess,
            )
        )

    if not scored:
        return candidates[0]
    return min(scored)[5]


def _best_minimax_guess(solver: WordleSolver, candidates: list[str], attempted: set[str]) -> str:
    candidate_set = set(candidates)
    scored: list[tuple[int, float, bool, float, str]] = []
    for guess in solver.guesses:
        if guess in attempted:
            continue
        partitions: dict[Feedback, int] = {}
        for answer in candidates:
            result = feedback_for(guess, answer)
            partitions[result] = partitions.get(result, 0) + 1
        total = len(candidates)
        entropy = sum((size / total) * log2(total / size) for size in partitions.values())
        scored.append(
            (
                max(partitions.values()),
                -entropy,
                guess not in candidate_set,
                -solver._frequency.get(guess, 0.0),
                guess,
            )
        )

    if not scored:
        return candidates[0]
    return min(scored)[4]


def _next_untried(
    solver: WordleSolver,
    candidates: list[str],
    attempted: set[str],
    aggressiveness: int,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None = None,
) -> str:
    ranked = _ranked_words(solver, candidates, aggressiveness, choice_cache)
    return next((word for word in ranked if word not in attempted), candidates[0])


def _ranked_words(
    solver: WordleSolver,
    candidates: list[str],
    aggressiveness: int,
    choice_cache: dict[tuple[object, ...], tuple[str, ...]] | None,
) -> tuple[str, ...]:
    key = ("rank", aggressiveness, tuple(solver.guesses), tuple(candidates))
    if choice_cache is not None and key in choice_cache:
        return choice_cache[key]
    ranked = tuple(
        score.word
        for score in solver.rank_guesses(
            candidates, limit=len(solver.guesses), aggressiveness=aggressiveness
        )
    )
    if choice_cache is not None:
        choice_cache[key] = ranked
    return ranked


def _remaining_after_guess(guess: str, candidates: list[str], answer: str) -> int:
    result = feedback_for(guess, answer)
    return sum(feedback_for(guess, candidate) == result for candidate in candidates)


def _aggressiveness_label(level: int) -> str:
    labels = {
        1: "conservative",
        2: "cautious",
        3: "balanced",
        4: "bold",
        5: "greedy",
    }
    return labels[level]


def format_feedback(result: Feedback) -> str:
    symbols = {0: "b", 1: "y", 2: "g"}
    return "".join(symbols[value] for value in result)


def parse_feedback(value: str) -> Feedback:
    aliases = {"b": 0, "g": 2, "y": 1, "0": 0, "1": 1, "2": 2, ".": 0}
    if len(value) != 5 or any(character not in aliases for character in value):
        raise ValueError("feedback must be five characters using g, y, b (or 2, 1, 0)")
    return tuple(aliases[character] for character in value)  # type: ignore[return-value]


def load_words(answer_path: Path | None, guess_path: Path | None) -> tuple[list[str], list[str]]:
    bundled_answers = Path(__file__).resolve().parents[2] / "data" / "solutions.txt"
    bundled_guesses = Path(__file__).resolve().parents[2] / "data" / "guesses.txt"
    answer_path = answer_path or (bundled_answers if bundled_answers.exists() else None)
    guess_path = guess_path or (bundled_guesses if bundled_guesses.exists() else None)

    if answer_path:
        answers = [word for word in read_word_file(answer_path) if _is_answer_word(word)]
    else:
        from wordfreq import top_n_list

        answers = [
            word
            for word in top_n_list("en", 100_000)
            if _is_answer_word(word) and _is_wordle_word(word)
        ]
    guesses = read_word_file(guess_path) if guess_path else answers
    return answers, guesses


def read_word_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _is_answer_word(word: str) -> bool:
    normalized = word.strip()
    if len(normalized) != 5 or not normalized.isalpha() or normalized != normalized.lower():
        return False
    return True


def _is_wordle_word(word: str) -> bool:
    from wordfreq import zipf_frequency

    # NYT answers can be uncommon (for example POSIT and GRIPE). Keep a broad
    # candidate set without opening the full obscure-token tail of wordfreq.
    return zipf_frequency(word, "en") >= 2.75


if __name__ == "__main__":
    main()
