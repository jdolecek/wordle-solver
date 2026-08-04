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

- **Benchmark all loaded Wordle solutions:** enter nothing; the solver runs all
	eleven strategies against every answer in the loaded solution list and reports
	average scores and solve rates. The lowest average score is the winner.
	It also writes a complete transcript to `mode3.log` in the current directory.
	Rankings for shared candidate states are cached, so equivalent branches across
	different answers are calculated only once.

- **Play with the solver:** choose one aggressiveness level from 1 to 5. Level 1
	is **conservative** and favors statistically likely answer words. Level 3
	blends likelihood and information gain. Level 5 is **greedy** and favors
	guesses that split the remaining answer set into the most informative
	feedback groups.
- **Solve a known answer:** enter the answer once; the solver automatically runs
	all five aggressiveness levels, then runs additional comparison strategies. The random
	strategy always uses the level-5 optimal opening word and randomly chooses a
	level from 1 to 5 for each later guess. It reports every path and score,
	followed by a summary showing the best deterministic score, the average for
	levels 1-5, the level-6 random score, and the level-7 adaptive score.

	Level 10 is a risk-averse minimax strategy using only accepted Wordle guesses.
	It minimizes the largest possible remaining answer group, then breaks ties by
	information gain and historical word frequency.

Level 11 directly minimizes expected remaining work. Its score is the expected
partition size, except that the all-green partition counts as zero because an
immediate correct answer ends the game. This small but important distinction
makes the objective align more closely with number of guesses than entropy does.

Levels 8 and 9 repeat levels 6 and 7 using only the supplied accepted-Wordle
guess list (`data/guesses.txt`) as their guess pool. Level 8 is random after
its optimal opening; level 9 adapts between frequency and entropy after its
historical-frequency opening.

Level 7 starts with the most statistically frequent historical answer word.
For every later guess it compares a frequency-ranked guess with an
entropy-ranked guess using the actual answer's feedback, keeps the method that
leaves fewer possible answers, and repeats that comparison on the next turn.

The known-answer paths use each aggressiveness setting at every turn. At each
turn they blend English-frequency likelihood with expected information gain,
then use worst-case partition size as a tie-breaker. These are greedy
mathematical strategies, not exhaustive proofs of the globally shortest path.

The solver tells you which guess to enter. After entering it in the online game, provide only its result. Use `g` for green, `y` for yellow, and `b` for gray:

```text
Opening guess: TRIES
Enter result for TRIES (g/y/b), or quit: bybgg
```

You may also use `2`, `1`, and `0` instead of letters. The solver prints the ten most likely remaining answers plus optimized information guesses with entropy, expected remaining candidates, and worst-case partition size.

For a controlled or official Wordle dictionary, put one word per line in
`data/solutions.txt` and optionally `data/guesses.txt`; these files are used
automatically when present. Answer entries are filtered to lowercase
five-letter words and words not ending in `s` as a conservative plural/name
filter. You can also provide them explicitly:

```sh
wordle-solver --answers data/answers.txt --guesses data/guesses.txt
```# wemos-D1-Heater
