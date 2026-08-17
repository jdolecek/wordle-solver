# Word Lists

The bundled `solutions.txt` contains the 2,315-word original public Wordle
solution set. Place the complete accepted-guess list in `guesses.txt` if
available. The solver automatically prefers these files over its
frequency-based fallback.

Answer entries are filtered to lowercase five-letter alphabetic words. Words
ending in `s` are retained because valid singular answers such as `glass`,
`class`, and `press` would otherwise be lost.

The New York Times can make editorial additions and removals, so this is not a
guarantee of its current internal candidate set. Replace the file with a newer
verified list when one is available.

`optimal_strategy.txt` is Alex Selby's published normal-mode decision tree for
this exact 2,315-answer set. It is only enabled when the loaded answers match
that set exactly.

The mobile app also offers two maintained NYT-oriented dictionaries:

- `nyt_wordlebot_answers.txt` contains 3,209 words treated as plausible answers
  by NYT WordleBot.
- `nyt_accepted_guesses.txt` contains 14,855 words accepted by NYT Wordle and is
  used as the probing-word pool. The mobile app can also treat this entire list
  as possible answers in its broad safety-net mode.

These two lists were imported on 2026-08-17 from WordGamesBot's maintained
`WordLists/NYT/Answers_with_ED.js` and `WordLists/NYT/Words.js` at upstream
revision `8aeba014054e9193f547e7b992f2f06662e79289`. Regenerate them with
`scripts/import_wordgamesbot_dictionaries.py`. They change over time and do not
carry the original dictionary's Level 12 optimality guarantee.

After updating either expanded dictionary, run
`scripts/build_dictionary_openings.py` to refresh the mobile app's precomputed
second-turn rankings.

You can also pass lists explicitly:

```sh
wordle-solver --answers data/solutions.txt --guesses data/guesses.txt
```
