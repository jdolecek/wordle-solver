from wordle_solver.cli import (
    _best_expected_turns_guess,
    collect_existing_history,
    format_feedback,
    load_optimal_policy,
    load_words,
)
from wordle_solver.core import WordleSolver, feedback_for


def test_duplicate_letters_follow_wordle_rules():
    assert feedback_for("allee", "apple") == (2, 1, 0, 0, 2)


def test_candidates_are_filtered_by_feedback():
    solver = WordleSolver(["cigar", "cairn", "cider", "rebut"])
    result = feedback_for("cigar", "cairn")
    assert solver.narrow([("cigar", result)]) == ["cairn"]


def test_ranked_guess_contains_entropy_metrics():
    solver = WordleSolver(["cigar", "cairn", "cider", "rebut"])
    scores = solver.rank_guesses(solver.answers, limit=2)
    assert len(scores) == 2
    assert scores[0].entropy >= 0
    assert scores[0].worst_case >= 1


def test_aggressiveness_changes_ranking_toward_information():
    solver = WordleSolver(["about", "cigar", "their", "which", "bland", "crane"], aggressiveness=1)
    conservative = solver.rank_guesses(solver.answers, limit=1)[0]
    greedy = solver.rank_guesses(solver.answers, limit=1, aggressiveness=5)[0]
    assert conservative.word == "about"
    assert greedy.word == "their"


def test_top_matches_are_ordered_by_likelihood():
    solver = WordleSolver(["about", "cigar", "their", "which"])
    matches = solver.top_matches(solver.answers)
    frequencies = [solver._frequency[word] for word in matches]
    assert frequencies == sorted(frequencies, reverse=True)


def test_builtin_dictionary_includes_less_frequent_wordle_words():
    answers, _ = load_words(None, None)
    assert {"bland", "posit", "gripe", "glass", "class"} <= set(answers)


def test_explicit_solution_file_is_used(tmp_path):
    answer_file = tmp_path / "solutions.txt"
    answer_file.write_text("bland\ncrane\nrules\nParis\n")
    answers, guesses = load_words(answer_file, None)
    assert answers == ["bland", "crane", "rules"]
    assert guesses == answers


def test_expected_turns_guess_accounts_for_immediate_solves():
    answers = ["cigar", "cider", "cairn"]
    solver = WordleSolver(answers, answers, include_answers_in_guesses=False)
    guess = _best_expected_turns_guess(solver, solver.answers, set())
    assert guess in answers


def test_information_ties_prefer_likely_remaining_answer():
    solver = WordleSolver(["probe", "prove"], ["about", "probe", "prove"], aggressiveness=5)
    assert solver.rank_guesses(solver.answers, limit=1)[0].word == "prove"


def test_existing_puzzle_history_is_collected(monkeypatch):
    solver = WordleSolver(["cigar", "cider"])
    entries = iter(["cigar", "ggbbg", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entries))

    history = collect_existing_history(solver)

    assert history == [("cigar", (2, 2, 0, 0, 2))]
    assert solver.narrow(history) == ["cider"]


def test_bundled_optimal_policy_has_published_score():
    policy, policy_answers = load_optimal_policy()
    assert policy[()] == "salet"
    scores = []
    for answer in policy_answers:
        history = []
        for turn in range(1, 6):
            guess = policy[tuple(history)]
            result = feedback_for(guess, answer)
            history.append(format_feedback(result).upper())
            if guess == answer:
                scores.append(turn)
                break
    assert len(scores) == 2315
    assert sum(scores) == 7920
    assert max(scores) == 5
