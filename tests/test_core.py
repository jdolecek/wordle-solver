from wordle_solver.cli import load_words
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
    assert greedy.word == "crane"


def test_top_matches_are_ordered_by_likelihood():
    solver = WordleSolver(["about", "cigar", "their", "which"])
    matches = solver.top_matches(solver.answers)
    frequencies = [solver._frequency[word] for word in matches]
    assert frequencies == sorted(frequencies, reverse=True)


def test_builtin_dictionary_includes_less_frequent_wordle_words():
    answers, _ = load_words(None, None)
    assert "bland" in answers
    assert "rules" not in answers


def test_explicit_solution_file_is_used(tmp_path):
    answer_file = tmp_path / "solutions.txt"
    answer_file.write_text("bland\ncrane\nrules\nParis\n")
    answers, guesses = load_words(answer_file, None)
    assert answers == ["bland", "crane"]
    assert guesses == answers