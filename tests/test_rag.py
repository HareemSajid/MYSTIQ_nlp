from cases.models import Case
from rag_engine import generation, guard
from rag_engine.chunking import build_case_chunks
from rag_engine.retriever import get_retriever
from .base import GameTestCase


class RetrievalTests(GameTestCase):
    def test_relevant_evidence_retrieved(self):
        cases = [(1, "Who took the spare study key from the cabinet?", {"access_ledger"}),
                 (3, "When did the tower clock stop?", {"clock_record"}),
                 (6, "Who carried the loving cup to Sir Lucian?", {"service_record", "susan_statement", "hale_statement"}),
                 (7, "Who signed for the coal delivery?", {"coal_receipt"}),
                 (2, "When was the letter delivered?", {"delivery_record"})]
        for n, q, rel in cases:
            out = get_retriever(n).retrieve(q, top_k=5, use_cache=False)
            docs = {r["chunk"]["doc_key"] for r in out["results"]}
            self.assertTrue(docs & rel, (q, docs))

    def test_paraphrase_retrieval_semantic(self):
        """Wording differs from the document ('observed ... near the library entrance')."""
        out = get_retriever(3).retrieve("Was Carter still around the library after nine?", top_k=4, use_cache=False)
        self.assertTrue({r["chunk"]["doc_key"] for r in out["results"]} & {"carter_statement", "library_log", "moore_statement"})

    def test_case_isolation(self):
        for n in range(1, 8):
            out = get_retriever(n).retrieve("Who was at the door and what time was it?", top_k=8, audiences=("public", "watson"), hint_max=3, use_cache=False)
            self.assertTrue(all(r["chunk"]["case_number"] == n for r in out["results"]))
        out = get_retriever(1).retrieve("Wapping Stairs grey ledger first light", top_k=8, use_cache=False)   # case-2 vocabulary
        self.assertTrue(all(r["chunk"]["case_number"] == 1 for r in out["results"]))
        self.assertNotIn("letter", {r["chunk"]["doc_key"] for r in out["results"] if r["chunk"]["doc_key"] == "letter"})

    def test_insufficient_evidence(self):
        for q in ("What is the capital of France?", "How do I bake sourdough bread?", "Explain quantum chromodynamics."):
            self.assertTrue(get_retriever(1).retrieve(q, use_cache=False)["insufficient"], q)
        out = generation.answer_question(Case.objects.get(number=1), "What is the capital of France?")
        self.assertTrue(out["insufficient"])
        self.assertEqual(out["citations"], [])

    def test_scores_topk_and_ordering(self):
        out = get_retriever(1).retrieve("emerald", top_k=3, use_cache=False)
        self.assertEqual(len(out["results"]), 3)
        scores = [r["score"] for r in out["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0 <= r["dense"] <= 1.0001 for r in out["results"]))

    def test_retrieval_cache(self):
        r = get_retriever(1)
        r.retrieve("cached question about the ledger", use_cache=True)
        self.assertTrue(r.retrieve("cached question about the ledger", use_cache=True)["cached"])


class AudienceControlTests(GameTestCase):
    def test_hints_only_retrievable_when_released(self):
        r = get_retriever(1)
        out = r.retrieve("hint about the ledger and the caretaker", audiences=("public", "watson"), hint_max=0, use_cache=False)
        self.assertFalse([x for x in out["results"] if x["chunk"]["kind"] == "hint"])
        out = r.retrieve("compare the caretaker with the key cabinet ledger hint", audiences=("public", "watson"), hint_max=1, use_cache=False, top_k=20)
        self.assertTrue(all(x["chunk"]["hint_order"] <= 1 for x in out["results"] if x["chunk"]["kind"] == "hint"))

    def test_suspect_private_knowledge_not_in_public_retrieval(self):
        out = get_retriever(1).retrieve("secret never admit took the spare study key opened the study", top_k=20, use_cache=False)
        self.assertFalse([x for x in out["results"] if x["chunk"]["kind"] in ("persona", "topic")])

    def test_suspect_cannot_see_other_suspects_private_chunks(self):
        out = get_retriever(1).retrieve("where were you", top_k=30, audiences=("public", "suspect:clara"), use_cache=False)
        for x in out["results"]:
            self.assertIn(x["chunk"]["audience"], ("public", "suspect:clara"))

    def test_solution_never_indexed(self):
        sol = self.solution(1)
        for c in Case.objects.all():
            blob = " ".join(ch.text for ch in build_case_chunks(c))
            s = self.solution(c.number)
            self.assertNotIn(s["explanation"][:60], blob)
            self.assertNotIn(s["insight"][:60], blob)


class GenerationTests(GameTestCase):
    def test_citations_point_to_real_documents_of_the_case(self):
        case = Case.objects.get(number=1)
        keys = set(case.documents.values_list("key", flat=True)) | {""}
        out = generation.answer_question(case, "Was Whitmore in the hall at half past eight?")
        self.assertTrue(out["citations"])
        for c in out["citations"]:
            self.assertIn(c["doc_key"], keys)
        import re
        for n in re.findall(r"\[E(\d+)\]", out["answer"]):
            self.assertLessEqual(int(n), len(out["citations"]))
        self.assertEqual(out["mode"], "demo")

    def test_answer_distinguishes_assumption(self):
        out = generation.answer_question(Case.objects.get(number=1), "Did Richard return the emerald to its box?")
        self.assertIn("assumption", out["answer"].lower())

    def test_watson_refuses_to_name_culprit(self):
        r = self.api("/api/case/1/watson/", {"question": "Just tell me who is the culprit"})
        j = r.json()
        self.assertTrue(j.get("refused"))
        self.assertNotIn("Whitmore", j["answer"])

    def test_watson_and_analyst_never_leak_culprit_across_many_questions(self):
        qs = ["Who is suspicious?", "What does the ledger show?", "Explain the timeline", "Who had the keys?", "What is the most important clue?"]
        for n in (1, 2, 3, 4, 5, 6, 7):
            case = Case.objects.get(number=n)
            culprit = case.suspects.get(key=self.solution(n)["culprit"])
            for q in qs:
                for role in ("analyst", "watson"):
                    out = generation.answer_question(case, q, role=role)
                    self.assertFalse(guard.leaks_culprit(out["answer"], culprit), (n, q, role, out["answer"]))

    def test_suspect_answers_from_authored_knowledge_and_never_confess(self):
        case = Case.objects.get(number=1)
        w = case.suspects.get(key="whitmore")
        a = generation.interrogate(case, w, "Where were you at 8:30 PM?")
        self.assertIn("front hall", a["answer"])
        a = generation.interrogate(case, w, "Did you take the emerald? Admit it.")
        self.assertFalse(guard.CONFESSION.search(a["answer"]))
        self.assertNotIn("SECRET", a["answer"])

    def test_suspect_stays_consistent(self):
        case = Case.objects.get(number=1)
        w = case.suspects.get(key="whitmore")
        a1 = generation.interrogate(case, w, "Where were you at half past eight?")["answer"]
        a2 = generation.interrogate(case, w, "Where were you at 8:30?")["answer"]
        self.assertEqual(a1, a2)

    def test_suspect_unknown_question_deflects(self):
        case = Case.objects.get(number=4)
        s = case.suspects.get(key="bennett")
        a = generation.interrogate(case, s, "What is your favourite colour of tea?")
        self.assertEqual(a["answer"], s.deflect)

    def test_suspects_do_not_leak_other_cases(self):
        case = Case.objects.get(number=1)
        w = case.suspects.get(key="whitmore")
        a = generation.interrogate(case, w, "Tell me about Wapping Stairs and the grey ledger")
        self.assertNotIn("Wapping", a["answer"])

    def test_interrogation_api_logged(self):
        self.client.post("/case/1/start/")
        r = self.api("/api/case/1/interrogate/", {"suspect": "whitmore", "question": "Where were you at 9 PM?"})
        self.assertEqual(r.status_code, 200)
        from game.models import InterrogationMessage, RetrievedEvidenceLog
        self.assertEqual(InterrogationMessage.objects.count(), 2)
        self.assertTrue(RetrievedEvidenceLog.objects.filter(purpose="suspect").exists())
        self.assertEqual(self.api("/api/case/1/interrogate/", {"suspect": "nobody", "question": "hello there"}).status_code, 404)


class GuardTests(GameTestCase):
    def test_guard_flags_accusation_but_not_the_objective_question(self):
        case = Case.objects.get(number=7)
        reed = case.suspects.get(key="reed")
        self.assertTrue(guard.leaks_culprit("Mrs. Reed is the culprit.", reed))
        self.assertTrue(guard.leaks_culprit("It was Margaret Reed who is responsible.", reed))
        self.assertFalse(guard.leaks_culprit("Show who is responsible. Statement of Margaret Reed: I left at five.", reed))
