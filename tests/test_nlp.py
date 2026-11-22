from cases.models import Case
from nlp_engine import answer_eval
from nlp_engine.coref import resolve
from nlp_engine.epistemic import classify
from nlp_engine.leakage import detect_leaks
from nlp_engine.lexicon import CaseLexicon
from nlp_engine.ner import entity_summary, extract_entities
from nlp_engine.nli import get_engine
from nlp_engine.reasoning import explain_statement
from nlp_engine.temporal import extract_times, annotate_times
from .base import GameTestCase


def mins(text, ctx=""):
    return [(t.minutes // 60, t.minutes % 60) for t in extract_times(text, ctx) if t.minutes is not None]


class TemporalTests(GameTestCase):
    def test_numeric_and_word_times(self):
        self.assertEqual(mins("9:20 PM"), [(21, 20)])
        self.assertEqual(mins("At approximately nine twenty, I observed Mr. Blake", "evening"), [(21, 20)])
        self.assertEqual(mins("a quarter to ten at night"), [(21, 45)])
        self.assertEqual(mins("twenty past eight in the evening"), [(20, 20)])
        self.assertEqual(mins("half past nine in the evening"), [(21, 30)])
        self.assertEqual(mins("five minutes to midnight"), [(23, 55)])
        self.assertEqual(mins("6:30 AM"), [(6, 30)])

    def test_ranges_and_non_times(self):
        self.assertEqual(mins("between 9:30 PM and 9:55 PM"), [(21, 30), (21, 55)])
        self.assertEqual(mins("Four tons of coal for ten pounds"), [])

    def test_ambiguity_and_precision_flags(self):
        t = extract_times("Come to the gate at ten")[0]
        self.assertTrue(t.ambiguous)
        t = extract_times("at about twenty to nine at dinner")[0]
        self.assertEqual(t.precision, "approximate")
        self.assertFalse(extract_times("9:20 PM")[0].ambiguous)

    def test_trailing_period_excluded_and_token_annotation(self):
        self.assertEqual(extract_times("It was 7:46 PM.")[0].text, "7:46 PM")
        self.assertIn("t2120", annotate_times("nine twenty in the evening"))

    def test_timeline_built_and_day_separated(self):
        c3 = Case.objects.get(number=3)
        days = set(c3.timeline.values_list("day_label", flat=True))
        self.assertTrue({"thursday", "saturday"} <= days)
        self.assertTrue(c3.timeline.filter(event_type="claim").exists() and c3.timeline.filter(event_type="record").exists())


class NERTests(GameTestCase):
    def setUp(self):
        super().setUp()
        self.lex = CaseLexicon.from_case(Case.objects.get(number=1))

    def test_entities_and_labels(self):
        s = entity_summary(extract_entities("Mr. Whitmore removed the spare key from the key cabinet in the pantry at 8:20 PM on Thursday.", self.lex))
        self.assertIn("Mr. Whitmore", s["PERSON"])
        self.assertIn("pantry", s["LOCATION"])
        self.assertIn("spare key", s["OBJECT"])
        self.assertIn("8:20 PM", s["TIME"])
        self.assertIn("Thursday", s["DATE"])

    def test_case_lexicon_corrects_spacy_errors(self):
        ents = extract_entities("Lord Ashford showed the emerald.", self.lex)
        self.assertEqual([e["label"] for e in ents if e["text"] == "Lord Ashford"], ["PERSON"])


class CorefTests(GameTestCase):
    def test_pronoun_resolution(self):
        lex = CaseLexicon.from_case(Case.objects.get(number=1))
        r = resolve("Mr. Whitmore entered the hall. He locked the door.", lex)
        self.assertEqual([p["person"] for p in r["resolved_pronouns"]], ["whitmore"])
        r = resolve("Eleanor looked at Richard. She assumed he had the emerald.", lex)
        self.assertEqual([p["person"] for p in r["resolved_pronouns"]], ["eleanor", "richard"])

    def test_role_descriptions_and_first_person(self):
        lex = CaseLexicon.from_case(Case.objects.get(number=4))
        r = resolve("The stout gentleman stood up. He took the old gentleman's arm.", lex)
        self.assertEqual(r["resolved_pronouns"][0]["person"], "bennett")
        self.assertIn("bennett", {c["person"] for c in r["clusters"]})
        lex1 = CaseLexicon.from_case(Case.objects.get(number=1))
        r = resolve("I called twice for a footman.", lex1, "clara")
        self.assertEqual(r["resolved_pronouns"][0]["person"], "clara")


class EpistemicTests(GameTestCase):
    def test_stances(self):
        self.assertEqual(classify("I assumed Richard had returned the emerald.")["stance"], "assumption")
        self.assertEqual(classify("I saw the emerald in my uncle's hand.")["stance"], "direct_observation")
        self.assertEqual(classify("Mr. Pym told me that a letter had come.")["stance"], "hearsay")
        self.assertEqual(classify("I did not see the gentleman get back on the train.")["stance"], "absence_of_observation")


class NLITests(GameTestCase):
    def cmp(self, n, p, ps, h, hs):
        return get_engine().compare(p, h, CaseLexicon.from_case(Case.objects.get(number=n)), ps, hs)

    def test_contradiction_hall_empty(self):
        r = self.cmp(1, "I took up my post in the front hall at eight o'clock. I remained at that post until half past nine.", "whitmore",
                     "At about half past eight I left the dining room for the hall. The hall was empty and nobody was at the front door.", "clara")
        self.assertEqual(r.label, "contradiction")

    def test_different_day_is_not_a_contradiction(self):
        r = self.cmp(3, "I left at 9:00 PM and locked the door from the outside.", "carter",
                     "On Thursday evening I saw William Carter inside the library at about twenty past nine.", "moore")
        self.assertEqual((r.label, r.finding), ("neutral", "different_day"))

    def test_same_day_same_event_is_contradiction(self):
        r = self.cmp(3, "I left at 9:00 PM on Saturday.", "carter", "On Saturday I saw William Carter inside the library at 9:20 PM.", "moore")
        self.assertEqual(r.label, "contradiction")

    def test_assumption_is_not_evidence(self):
        r = self.cmp(1, "I assumed Richard had returned the emerald to its box.", "eleanor", "I never said that I had touched the emerald, and I did not.", "richard")
        self.assertEqual(r.label, "neutral")

    def test_absence_of_observation_not_contradiction(self):
        r = self.cmp(4, "I did not see the gentleman in the brown overcoat get back on the train.", "mills",
                     "At the whistle the stout gentleman came back alone and sat down.", "shaw")
        self.assertEqual(r.label, "neutral")

    def test_literal_truth_misleading(self):
        r = self.cmp(5, "After that I never touched his key again.", "mary", "Had a second key cut for Mary.", None)
        self.assertEqual((r.label, r.finding), ("neutral", "literal_vs_implied"))

    def test_stopped_clock_cannot_strike(self):
        r = self.cmp(3, "I heard the tower clock strike ten.", "grey", "The clock was found stopped at 9:10. A stopped clock does not strike.", None)
        self.assertEqual(r.label, "contradiction")

    def test_reference_resolution_feeds_nli(self):
        r = self.cmp(6, "I never rose from my chair and I did not go near the sideboard.", "mills",
                     "9:02 PM — Tilling notes that the gentleman at the foot of the table rises and crosses to the sideboard.", None)
        self.assertEqual(r.label, "contradiction")

    def test_unrelated_statements_neutral(self):
        r = self.cmp(2, "I heard nothing of any letter until Saturday.", "blake", "I know nothing about the weather.", "margaret")
        self.assertEqual(r.label, "neutral")

    def test_explain_pipeline_finds_source_documents(self):
        case = Case.objects.get(number=1)
        st = case.statements.get(order=1)           # Whitmore: never touched the key cabinet
        out = explain_statement(case, st.text, "whitmore", "whitmore_statement")
        contra = [c for c in out["comparisons"] if c["label"] == "contradiction"]
        self.assertTrue(contra)
        self.assertEqual(contra[0]["doc_key"], "access_ledger")
        self.assertTrue(out["summary"])

    def test_explain_flags_false_leads_not_contradictions(self):
        case = Case.objects.get(number=3)
        st = case.statements.filter(suspect__key="moore").first()
        out = explain_statement(case, st.text, "moore", "moore_statement")
        self.assertFalse([c for c in out["comparisons"] if c["label"] == "contradiction"])
        self.assertTrue([c for c in out["comparisons"] if c["finding"] == "different_day"])


class LeakageTests(GameTestCase):
    def test_only_blake_flagged_in_case_two(self):
        case = Case.objects.get(number=2)
        flagged = {st.suspect.key for st in case.statements.select_related("suspect") if detect_leaks(case, st.text, st.suspect.key)["flagged"]}
        self.assertEqual(flagged, {"blake"})

    def test_no_false_alarms_in_other_cases(self):
        for n in (1, 3, 4, 5, 6, 7):
            case = Case.objects.get(number=n)
            for st in case.statements.select_related("suspect"):
                self.assertFalse(detect_leaks(case, st.text, st.suspect.key)["flagged"], (n, st.text))


class AnswerEvaluationTests(GameTestCase):
    def evaluate(self, n, **over):
        sub = self.correct_submission(n)
        sub.update(over)
        case = Case.objects.get(number=n)
        from rag_engine.retriever import get_retriever
        return answer_eval.evaluate(self.solution(n), list(case.suspects.all()), sub, get_retriever(n).embedder)

    def test_canonical_answer_solves_every_case(self):
        for n in range(1, 8):
            self.assertTrue(self.evaluate(n)["solved"], n)

    def test_wrong_culprit_never_solves(self):
        for n in range(1, 8):
            case = Case.objects.get(number=n)
            wrong = next(s.key for s in case.suspects.all() if s.key != self.solution(n)["culprit"])
            self.assertFalse(self.evaluate(n, culprit=wrong)["solved"], n)

    def test_paraphrased_explanation_scores_semantically(self):
        ev = self.evaluate(1, explanation="Whitmore claimed he never left the hall, but Mr. Dunmore's ledger records him taking the spare study key at twenty past eight, and Clara found the hall deserted. Eleanor merely guessed about Richard.")
        self.assertGreaterEqual(ev["explanation_fraction"], 0.66)

    def test_irrelevant_explanation_scores_low(self):
        ev = self.evaluate(1, explanation="Eleanor is in debt so she must have wanted the money.")
        self.assertLessEqual(ev["explanation_fraction"], 0.34)

    def test_evidence_recall_precision(self):
        ev = self.evaluate(1, evidence=["invitation"])
        self.assertEqual(ev["evidence_recall"], 0.0)
        self.assertTrue(ev["missing_evidence"])


class EpistemicRegressionTests(GameTestCase):
    def test_told_me_nothing_is_a_denial_not_hearsay(self):
        self.assertNotEqual(classify("Edward told me nothing.")["stance"], "hearsay")
        self.assertNotEqual(classify("He never told me about the letter.")["stance"], "hearsay")
        self.assertEqual(classify("Mr. Pym told me on Friday that a letter had come.")["stance"], "hearsay")

    def test_heard_nothing_is_absence_of_observation(self):
        self.assertEqual(classify("I heard nothing of any letter until you told me on Saturday.")["stance"], "absence_of_observation")
