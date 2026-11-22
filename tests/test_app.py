import json
from django.contrib.auth.models import User
from django.test import Client
from cases.models import Case, CaseSolution
from game.models import Score
from .base import GameTestCase


class AccountTests(GameTestCase):
    def test_registration_creates_user_with_hashed_password_and_profile(self):
        c = Client()
        r = c.post("/accounts/register/", {"username": "watson", "password1": "Doctor-221b-x", "password2": "Doctor-221b-x"})
        self.assertRedirects(r, "/dashboard/")
        u = User.objects.get(username="watson")
        self.assertTrue(u.password.startswith(("pbkdf2_", "argon2", "bcrypt")))
        self.assertNotIn("Doctor-221b-x", u.password)
        self.assertTrue(hasattr(u, "profile"))

    def test_weak_password_rejected(self):
        r = Client().post("/accounts/register/", {"username": "x1", "password1": "12345678", "password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="x1").exists())

    def test_login_logout(self):
        c = Client()
        self.assertEqual(c.get("/dashboard/").status_code, 302)
        self.assertTrue(c.login(username="holmes", password="Baker-Street-221b"))
        self.assertEqual(c.get("/dashboard/").status_code, 200)
        c.post("/accounts/logout/")
        self.assertEqual(c.get("/dashboard/").status_code, 302)

    def test_public_pages(self):
        for url in ("/", "/how-to-play/", "/accounts/login/", "/accounts/register/"):
            self.assertEqual(Client().get(url).status_code, 200, url)


class CaseDataTests(GameTestCase):
    def test_seven_cases_loaded_with_required_structure(self):
        self.assertEqual(Case.objects.count(), 7)
        for c in Case.objects.all():
            self.assertGreaterEqual(c.suspects.count(), 4)
            self.assertEqual(c.hints.count(), 3, c.title)
            self.assertGreaterEqual(c.documents.count(), 8)
            sol = self.solution(c.number)
            self.assertGreaterEqual(len(sol["required_evidence"]), 3)
            keys = set(c.documents.values_list("key", flat=True))
            self.assertTrue(set(sol["required_evidence"]) <= keys, c.title)
            self.assertTrue(set(sol.get("related_evidence", [])) <= keys, c.title)
            self.assertIn(sol["culprit"], set(c.suspects.values_list("key", flat=True)))
            for opt in ("what_options", "when_options", "insight_options"):
                self.assertEqual(sum(o["correct"] for o in sol[opt]), 1, (c.title, opt))
            self.assertGreater(c.timeline.count(), 5)

    def test_case_five_has_five_suspects_in_case_seven(self):
        self.assertEqual(Case.objects.get(number=7).suspects.count(), 5)

    def test_hints_never_name_the_culprit(self):
        for c in Case.objects.all():
            culprit = c.suspects.get(key=self.solution(c.number)["culprit"])
            h3 = c.hints.get(order=1).text.lower() + c.hints.get(order=2).text.lower()
            self.assertNotIn(culprit.name.split()[-1].lower(), h3, c.title)


class ProgressionTests(GameTestCase):
    def test_levels_unlock_in_sequence(self):
        self.assertEqual(self.client.get("/case/1/").status_code, 200)
        self.assertEqual(self.client.get("/case/2/").status_code, 403)
        self.assertEqual(self.client.get("/case/2/investigate/").status_code, 403)
        self.assertEqual(self.client.get("/case/2/evidence/letter/").status_code, 403)
        self.assertEqual(self.api("/api/case/2/ask/", {"question": "what is the letter"}).status_code, 403)
        self.solve(1)
        self.assertEqual(self.client.get("/case/2/").status_code, 200)
        self.assertEqual(self.client.get("/case/3/").status_code, 403)

    def test_reveal_unlocks_next_but_scores_zero(self):
        self.client.post("/case/1/start/")
        self.client.post("/case/1/reveal/")
        self.assertEqual(self.client.get("/case/2/").status_code, 200)
        s = Score.objects.get(user=self.user, case__number=1)
        self.assertFalse(s.solved)
        self.assertEqual(s.points, 0)

    def test_progress_persistence(self):
        self.client.post("/case/1/start/")
        self.api("/api/case/1/important/", {"doc_key": "access_ledger"})
        self.api("/api/case/1/notebook/", {"text": "Whitmore lied about the hall"})
        r = self.client.get("/case/1/investigate/")
        self.assertContains(r, "Whitmore lied about the hall")
        self.assertContains(r, 'data-star="access_ledger"')
        self.assertIn("access_ledger", self.user.progress.get(case__number=1).important_docs)
        self.api("/api/case/1/important/", {"doc_key": "access_ledger"})   # toggle off
        self.assertEqual(self.user.progress.get(case__number=1).important_docs, [])

    def test_evidence_viewer_and_suspect_pages(self):
        self.client.post("/case/1/start/")
        r = self.client.get("/case/1/evidence/access_ledger/")
        self.assertContains(r, "Key Cabinet Ledger")
        self.assertContains(r, "Mark as Important")
        self.assertEqual(self.client.get("/case/1/evidence/nope/").status_code, 404)
        self.assertEqual(self.client.get("/case/1/suspect/whitmore/").status_code, 200)
        self.assertEqual(self.client.get("/case/1/evidence/letter/").status_code, 404)   # other case's doc


class HintTests(GameTestCase):
    def test_exactly_three_hints_in_order_and_recorded(self):
        self.client.post("/case/1/start/")
        for i in (1, 2, 3):
            r = self.api("/api/case/1/hint/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["order"], i)
        self.assertEqual(self.api("/api/case/1/hint/").status_code, 409)
        self.assertEqual(self.user.progress.get(case__number=1).hints_used, 3)

    def test_hints_reduce_score(self):
        self.solve(2)       # not allowed (locked) -> nothing happens
        self.assertFalse(Score.objects.filter(user=self.user, solved=True).exists())
        self.client.post("/case/1/start/")
        base = self.client.post("/case/1/deduce/", self.correct_submission(1))
        s0 = Score.objects.get(user=self.user, case__number=1).points
        # fresh user with 2 hints
        u2 = User.objects.create_user("w2", password="Baker-Street-221b")
        from django.test import Client
        c2 = Client(); c2.login(username="w2", password="Baker-Street-221b")
        c2.post("/case/1/start/")
        for _ in range(2):
            c2.post("/api/case/1/hint/", content_type="application/json", data="{}")
        c2.post("/case/1/deduce/", self.correct_submission(1))
        s2 = Score.objects.get(user=u2, case__number=1).points
        self.assertEqual(s0 - s2, 150)


class DeductionTests(GameTestCase):
    def test_correct_deduction_solves_and_scores(self):
        r = self.solve(1)
        self.assertRedirects(r, "/case/1/results/")
        s = Score.objects.get(user=self.user, case__number=1)
        self.assertTrue(s.solved)
        self.assertGreaterEqual(s.points, 600)
        self.assertLessEqual(s.points, 1000)

    def test_wrong_culprit_not_solved_and_no_leak(self):
        self.client.post("/case/1/start/")
        sub = self.correct_submission(1)
        sub["culprit"] = "eleanor"
        r = self.client.post("/case/1/deduce/", sub)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "not yet proven")
        self.assertNotContains(r, "Whitmore left his post")
        self.assertFalse(Score.objects.filter(user=self.user, case__number=1, solved=True).exists())
        self.assertRedirects(self.client.get("/case/1/results/"), "/case/1/investigate/")

    def test_correct_culprit_with_empty_reasoning_not_enough(self):
        self.client.post("/case/1/start/")
        sub = {"culprit": self.solution(1)["culprit"], "what": "b", "when": "a", "insight": "b", "evidence": [], "explanation": ""}
        r = self.client.post("/case/1/deduce/", sub)
        self.assertEqual(r.status_code, 200)

    def test_attempt_penalty(self):
        self.client.post("/case/1/start/")
        bad = self.correct_submission(1); bad["culprit"] = "clara"
        self.client.post("/case/1/deduce/", bad)
        self.client.post("/case/1/deduce/", self.correct_submission(1))
        s = Score.objects.get(user=self.user, case__number=1)
        self.assertEqual(s.attempt_penalty, 40)

    def test_answer_key_not_exposed(self):
        self.client.post("/case/1/start/")
        page = self.client.get("/case/1/deduce/").content.decode()
        self.assertNotIn('"correct"', page)
        self.assertNotIn("correct: true", page.lower())
        for url in ("/case/1/investigate/", "/case/1/evidence/access_ledger/", "/case/1/"):
            body = self.client.get(url).content.decode()
            self.assertNotIn("required_evidence", body)
            self.assertNotIn(self.solution(1)["explanation"][:40], body)
        sol_text = self.solution(1)["what"][:40]
        r = self.api("/api/case/1/ask/", {"question": "what happened to the emerald"})
        self.assertNotIn(sol_text, r.content.decode())

    def test_results_show_everything_after_solving(self):
        self.solve(1)
        r = self.client.get("/case/1/results/")
        for text in ("SOLVED", "James Whitmore", "Actual sequence of events", "Supporting evidence", "Next: The Midnight Letter"):
            self.assertContains(r, text)

    def test_full_seven_case_journey_and_final_report(self):
        for n in range(1, 8):
            self.assertRedirects(self.solve(n), f"/case/{n}/results/")
        self.assertEqual(Score.objects.filter(user=self.user, solved=True).count(), 7)
        r = self.client.get("/report/")
        self.assertContains(r, "DETECTIVE MASTER")
        self.assertContains(r, "7 / 7")
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)


class ApiTests(GameTestCase):
    def test_explain_compare_and_evidence_analysis_endpoints(self):
        self.client.post("/case/1/start/")
        from cases.models import Statement
        sts = list(Statement.objects.filter(case__number=1))
        r = self.api("/api/case/1/explain/", {"statement_id": sts[1].id})
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIn("comparisons", j)
        self.assertIn("summary", j)
        self.assertTrue(any(c["label"] == "contradiction" for c in j["comparisons"]))
        r = self.api("/api/case/1/compare/", {"a": sts[0].id, "b": sts[4].id})
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.json()["label"], ("contradiction", "neutral", "entailment"))
        self.assertEqual(self.api("/api/case/1/compare/", {"a": sts[0].id, "b": sts[0].id}).status_code, 400)
        r = self.client.get("/api/case/1/evidence/whitmore_statement/analysis/")
        j = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertIn("PERSON", j["entity_summary"])
        self.assertTrue(j["times"])
        self.assertIn("<mark", j["highlighted"])
        self.assertEqual(self.client.get("/api/case/1/evidence/letter/analysis/").status_code, 404)

    def test_other_cases_statements_not_accessible_via_api(self):
        from cases.models import Statement
        other = Statement.objects.filter(case__number=3).first()
        self.client.post("/case/1/start/")
        self.assertEqual(self.api("/api/case/1/explain/", {"statement_id": other.id}).status_code, 404)

    def test_api_requires_login_and_validates_input(self):
        from django.test import Client
        self.assertEqual(Client().post("/api/case/1/ask/", data="{}", content_type="application/json").status_code, 401)
        self.assertEqual(self.api("/api/case/1/ask/", {"question": "x"}).status_code, 400)
        self.assertEqual(self.api("/api/case/1/watson/", {"question": ""}).status_code, 400)

    def test_status_endpoint_reports_backends_honestly(self):
        j = self.client.get("/api/status/").json()
        self.assertIn("embedder", j)
        self.assertIn("nli", j)
        self.assertFalse(j["gemini"])

    def test_ask_returns_scores_and_latency(self):
        self.client.post("/case/1/start/")
        j = self.api("/api/case/1/ask/", {"question": "Who took the spare key?"}).json()
        self.assertIn("latency_ms", j)
        self.assertTrue(all("similarity" in c and "score" in c for c in j["citations"]))
        self.assertIn("stages_ms", j["retrieval"])
