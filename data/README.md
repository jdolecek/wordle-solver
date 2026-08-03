# Word Lists

Place the official/current Wordle answer list in `solutions.txt`, one lowercase
five-letter word per line. Place the complete accepted-guess list in
`guesses.txt` if available. The solver automatically prefers these files over
its frequency-based fallback.

Answer entries are filtered to lowercase five-letter words and words that do
not end in `s`, which excludes capitalized proper-name-looking entries and
common plural forms. The guess list remains broader because plural words can
still be useful as information probes.

The solver does not include a copied proprietary or unofficial list. The
classic public answer snapshot commonly circulated online contains about 2,315
words, while newer snapshots are often reported as roughly 3,189 words. Verify
the source and count of any list before using it for a specific Wordle version.

You can also pass lists explicitly:

```sh
wordle-solver --answers data/solutions.txt --guesses data/guesses.txt
```