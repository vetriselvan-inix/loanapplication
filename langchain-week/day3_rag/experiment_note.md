# Experiment note: chunk size 300 against 80

All ten policy questions were run at both sizes (see `answers_chunk300.md`, `answers_chunk80.md` and `experiment_comparison.md`).

1. Eight of ten answers changed when the chunk size went from 300 to 80, but only four changed in substance: questions 3, 5, 7 and 10.
2. Question 10 was a retrieval failure: at 80, the three slots filled with overlapping fragments of rule 1.3, so the rate rule 3.1 was never retrieved and the model rightly said it could not find it.
3. Questions 5 and 7 were chunking failures: fragments lost the section number (the answer cited "[Context line 2]") or the end of a sentence ("after documents", without "verified").
4. Question 3 was a model failure, not retrieval: section 3.2 was retrieved first, but our "no calculations, no made-up figures" rule made the model say "I could not find this" while quoting 3.2 in the same answer.
5. At 300 each chunk holds whole rules, so all ten pass; the way to tell a retrieval problem from a model problem is to print the retrieved chunks before changing anything.
