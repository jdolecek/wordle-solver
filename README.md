# Wordle Solver

An interactive Python Wordle solver that explains each recommendation.

## How the ranking works

1. **Filter:** each entered guess and color pattern removes every answer whose exact Wordle feedback does not match.
2. **Information gain:** each candidate guess partitions the remaining answers by the feedback pattern it could produce. The solver computes Shannon entropy for those partitions. Higher entropy means the guess is expected to eliminate more possibilities.
3. **Worst-case protection:** ties favor guesses with a smaller largest partition, limiting how bad the unlucky outcome can be.
4. **Likely answers:** the separate top-10 list is ordered from most to least statistically likely using `wordfreq` English Zipf frequency scores, so it highlights plausible answers rather than only broad probing words. Ties are alphabetical and therefore deterministic.

For large candidate sets, the solver first keeps the strongest 300 guesses using distinct-letter and positional-frequency heuristics, then calculates exact entropy for those. Once the set is small, it evaluates the full guess dictionary. The built-in fallback dictionary includes less frequent playable words such as `bland` while filtering the obscure tail of the general English list; for exact behavior, provide the game's accepted answer and guess lists with `--answers` and `--guesses`.

## Setup

```sh
cd wordle-solver
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
pytest
```

## Run

```sh
wordle-solver
```

At startup, choose one of three modes:

- **Benchmark all loaded Wordle solutions:** the solver runs the four retained
	strategies (Levels 5, 10, 11, and 12) against every answer in the loaded solution list and reports
	average scores and solve rates. The lowest average score is the winner.
	It also writes a complete transcript to `mode3.log` in the current directory.
	Rankings for shared candidate states are cached, so equivalent branches across
	different answers are calculated only once.

- **Play with the solver:** with the bundled answer set, the solver follows the
	provably optimal Level 12 decision tree. Custom dictionaries fall back to the
	greedy Level 5 information strategy.
- **Solve a known answer:** enter the answer once; the solver automatically runs
	all four retained comparison strategies and reports every path and score.

- **Resume a puzzle:** enter every guess you have already played and its `g/y/b`
	feedback. The solver validates the combined history, narrows the answer list,
	and continues with recommendations from the current puzzle state.

	Level 10 is a risk-averse minimax strategy using only accepted Wordle guesses.
	It minimizes the largest possible remaining answer group, then breaks ties by
	information gain and historical word frequency.

Level 11 directly minimizes expected remaining work. Its score is the expected
partition size, except that the all-green partition counts as zero because an
immediate correct answer ends the game. This small but important distinction
makes the objective align more closely with number of guesses than entropy does.

Level 12 follows Alex Selby's published exact normal-mode decision tree. For
the bundled 2,315 answers it starts with `SALET`, requires exactly 7,920 total
guesses (3.42117 average), and solves every answer within five guesses. The
result is globally optimal under a uniform answer probability and the original
12,972-word accepted-guess set.

Level 5 uses expected information gain with worst-case partition size as a
tie-breaker. These are greedy mathematical strategies, not exhaustive proofs
of the globally shortest path.

The solver tells you which guess to enter. After entering it in the online game, provide only its result. Use `g` for green, `y` for yellow, and `b` for gray:

```text
Opening guess: TRIES
Enter result for TRIES (g/y/b), or quit: bybgg
```

You may also use `2`, `1`, and `0` instead of letters. The solver prints the ten most likely remaining answers plus optimized information guesses with entropy, expected remaining candidates, and worst-case partition size.

For a controlled or official Wordle dictionary, put one word per line in
`data/solutions.txt` and optionally `data/guesses.txt`; these files are used
automatically when present. The bundled 2,315-word public solution set includes
words such as `posit`, `gripe`, and `prove`, without admitting proper names from
the frequency-based fallback. Answer entries are filtered to lowercase
five-letter alphabetic words. You can also provide lists explicitly:

```sh
wordle-solver --answers data/answers.txt --guesses data/guesses.txt
```# wemos-D1-Heater
