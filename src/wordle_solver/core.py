from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log2

Feedback = tuple[int, int, int, int, int]


def feedback_for(guess: str, answer: str) -> Feedback:
    """Return Wordle feedback: 2 green, 1 yellow, 0 gray.

    The second pass consumes letters from the answer, which handles duplicate
    letters exactly as the game does.
    """
    guess = guess.lower()
    answer = answer.lower()
    result = [0] * 5
    remaining = Counter()

    for index, (guess_letter, answer_letter) in enumerate(zip(guess, answer)):
        if guess_letter == answer_letter:
            result[index] = 2
        else:
            remaining[answer_letter] += 1

    for index, guess_letter in enumerate(guess):
        if result[index] == 0 and remaining[guess_letter] > 0:
            result[index] = 1
            remaining[guess_letter] -= 1

    return tuple(result)  # type: ignore[return-value]


def filter_candidates(words: list[str], guess: str, result: Feedback) -> list[str]:
    return [word for word in words if feedback_for(guess, word) == result]


@dataclass(frozen=True)
class GuessScore:
    word: str
    entropy: float
    expected_remaining: float
    worst_case: int


class WordleSolver:
    def __init__(
        self,
        answers: list[str],
        guesses: list[str] | None = None,
        aggressiveness: int = 5,
        include_answers_in_guesses: bool = True,
    ):
        if aggressiveness not in range(1, 6):
            raise ValueError("aggressiveness must be between 1 and 5")
        self.answers = sorted({word.lower() for word in answers if _valid_word(word)})
        self.guesses = {word.lower() for word in (guesses or []) if _valid_word(word)}
        if include_answers_in_guesses:
            self.guesses |= set(self.answers)
        self.guesses = sorted(self.guesses)
        self.aggressiveness = aggressiveness
        self._frequency = _word_frequency(self.guesses)

    def narrow(self, history: list[tuple[str, Feedback]]) -> list[str]:
        candidates = self.answers
        for guess, result in history:
            candidates = filter_candidates(candidates, guess, result)
        return candidates

    def top_matches(self, candidates: list[str], limit: int = 10) -> list[str]:
        """Return likely answers in descending English-frequency order."""
        return sorted(candidates, key=lambda word: (-self._frequency[word], word))[:limit]

    def rank_guesses(
        self, candidates: list[str], limit: int = 10, aggressiveness: int | None = None
    ) -> list[GuessScore]:
        if not candidates:
            return []
        level = self.aggressiveness if aggressiveness is None else aggressiveness
        if level not in range(1, 6):
            raise ValueError("aggressiveness must be between 1 and 5")

        pool = self._guess_pool(candidates)
        scored = [self._score_guess(guess, candidates) for guess in pool]
        entropy_values = [score.entropy for score in scored]
        frequency_values = [self._frequency[score.word] for score in scored]
        entropy_min, entropy_max = min(entropy_values), max(entropy_values)
        frequency_min, frequency_max = min(frequency_values), max(frequency_values)
        entropy_span = entropy_max - entropy_min or 1.0
        frequency_span = frequency_max - frequency_min or 1.0
        information_weight = (level - 1) / 4

        def priority(score: GuessScore) -> float:
            information = (score.entropy - entropy_min) / entropy_span
            likelihood = (self._frequency[score.word] - frequency_min) / frequency_span
            return information * information_weight + likelihood * (1 - information_weight)

        return sorted(
            scored,
            key=lambda score: (-priority(score), score.worst_case, score.expected_remaining, score.word),
        )[:limit]

    def _guess_pool(self, candidates: list[str]) -> list[str]:
        # Exact entropy across a large dictionary is expensive. A letter/position
        # pre-score keeps the interactive command fast, then exact entropy ranks
        # only the strongest broad-information guesses.
        if len(candidates) <= 500:
            return self.guesses
        letter_counts = Counter(letter for word in candidates for letter in set(word))
        position_counts = Counter((index, letter) for word in candidates for index, letter in enumerate(word))

        def heuristic(word: str) -> float:
            unique = sum(letter_counts[letter] for letter in set(word))
            positional = sum(position_counts[index, letter] for index, letter in enumerate(word))
            return unique + positional * 0.35

        return sorted(self.guesses, key=lambda word: (-heuristic(word), word))[:300]

    @staticmethod
    def _score_guess(guess: str, candidates: list[str]) -> GuessScore:
        partitions: Counter[Feedback] = Counter(feedback_for(guess, answer) for answer in candidates)
        total = len(candidates)
        entropy = sum((size / total) * log2(total / size) for size in partitions.values())
        expected_remaining = sum(size * size for size in partitions.values()) / total
        return GuessScore(guess, entropy, expected_remaining, max(partitions.values()))


def _valid_word(word: str) -> bool:
    return len(word) == 5 and word.isalpha()


def _word_frequency(words: list[str]) -> dict[str, float]:
    try:
        from wordfreq import zipf_frequency

        return {word: zipf_frequency(word, "en") for word in words}
    except ImportError:
        return {word: 0.0 for word in words}