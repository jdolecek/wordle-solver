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

You can also pass lists explicitly:

```sh
wordle-solver --answers data/solutions.txt --guesses data/guesses.txt
```
