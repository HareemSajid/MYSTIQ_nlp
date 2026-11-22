# Setup, running and testing (Windows)

## 1. One-time setup
```bat
setup.bat
```
(creates `venv`, installs `requirements.txt`, downloads the spaCy model, creates `.env`, migrates, loads the 7 cases, builds the vector indexes).
Manual equivalent: see README.

## 2. Optional: pretrained models (recommended for best quality)
```bat
venv\Scripts\activate
pip install sentence-transformers
python manage.py build_index
python manage.py evaluate_nlp
```
This switches retrieval to `all-MiniLM-L6-v2` and NLI to `cross-encoder/nli-MiniLM2-L6-H768` (first run downloads ~100–300 MB).
Check `http://127.0.0.1:8000/api/status/` (shows the active embedder / NLI backend).

## 3. Optional: Gemini
Put `GEMINI_API_KEY=...` in `.env` and restart. Without it the app runs in clearly labelled demo mode (answers are still grounded in retrieved evidence).

## 4. Run
```bat
run.bat      (or: python manage.py runserver)
```
Open http://127.0.0.1:8000/

## 5. Automated tests (67+)
```bat
python manage.py test tests
```
Covers registration/login, case data integrity, level unlocking, progress persistence, evidence access, hints, scoring, deduction,
answer-key secrecy, a full 7-case journey, RAG relevance / isolation / citations / insufficient evidence / audience control,
Watson & suspect guards, NER, temporal, coreference, NLI, leakage and semantic answer evaluation.

## 6. NLP evaluation (regenerates docs/NLP_EVALUATION_REPORT.md)
```bat
python manage.py evaluate_nlp
```

## 7. Manual browser checklist (the JavaScript UI was not click-tested by the author)
1. Register → Dashboard shows 7 cards, only Case 1 open.
2. Case 1 → Start → Investigation Room: click every tab (hash in URL persists on refresh).
3. Evidence tab: open a document → "Show NLP analysis" (entities highlighted, times table) → ask "Who took the spare key?" (answer has E1/E2 links).
4. Evidence tab: ★ toggles; refresh → star persists.
5. Statements tab: "Why is this suspicious?" on Whitmore's 2nd statement (contradiction vs ledger); on Eleanor (assumption); Compare two statements.
6. Timeline tab: check day grouping and "inferred" badges.
7. Interrogation tab: ask Whitmore "Where were you at 8:30?" and "Why does the ledger show you took the key?"; try presenting evidence.
8. Dr. Watson: ask "what does the ledger show?", request hints 1-3 (confirm dialog, counter, 4th disabled).
9. Final Deduction: submit a wrong culprit (feedback, no answer leaked) then the right one → Results page.
10. Case 2 unlocks. Test on a phone-width window (responsive) and with keyboard Tab (focus rings).

## 8. Screenshots
`docs/screens/` contains 18 reference renders of every screen (landing, auth, dashboard, case intro, the 7 investigation tabs, evidence viewer with NLP analysis, suspect profile, final deduction feedback, results, final report).
They were produced with a static HTML renderer (WeasyPrint) from the real server output, so the real browser will differ slightly (fonts, gas-lamp glow and fog animations, scrolling chat boxes).
