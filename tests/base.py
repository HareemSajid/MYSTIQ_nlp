from django.contrib.auth.models import User
from django.test import Client, TestCase
from cases.loader import load_all
from cases.models import Case, CaseSolution
from rag_engine.retriever import reset_retrievers


class GameTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_all()
        reset_retrievers()
        cls.user = User.objects.create_user("holmes", password="Baker-Street-221b")

    def setUp(self):
        self.client = Client()
        self.client.login(username="holmes", password="Baker-Street-221b")

    # helpers
    def solution(self, n):
        return CaseSolution.objects.get(case__number=n).data

    def correct_submission(self, n):
        sol = self.solution(n)
        pick = lambda key: next(o["id"] for o in sol[key] if o["correct"])
        return {"culprit": sol["culprit"], "what": pick("what_options"), "when": pick("when_options"),
                "insight": pick("insight_options"), "evidence": sol["required_evidence"],
                "explanation": sol["explanation"]}

    def solve(self, n):
        self.client.post(f"/case/{n}/start/")
        return self.client.post(f"/case/{n}/deduce/", self.correct_submission(n))

    def api(self, url, body=None):
        import json
        return self.client.post(url, data=json.dumps(body or {}), content_type="application/json")
