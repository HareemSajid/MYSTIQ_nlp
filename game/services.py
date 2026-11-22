"""Game rules: unlocking, scoring, final deduction and summaries. None of this calls an LLM."""
from django.db.models import Sum
from django.utils import timezone

from cases.models import Case, CaseSolution, Hint
from nlp_engine import answer_eval
from .models import FinalDeduction, HintUsage, PlayerProgress, Score

HINT_PENALTY = 75
ATTEMPT_PENALTY = 40
TIME_FREE_MINUTES = 10
TIME_PENALTY_PER_MIN = 5
TIME_PENALTY_CAP = 150
MAX_SECONDS = 2 * 3600


def progress_for(user, case):
    p, _ = PlayerProgress.objects.get_or_create(user=user, case=case)
    return p


def is_unlocked(user, case):
    if case.number == 1:
        return True
    prev = Case.objects.filter(number=case.number - 1).first()
    if not prev:
        return False
    return PlayerProgress.objects.filter(user=user, case=prev, finished_at__isnull=False).exists()


def start_case(user, case):
    p = progress_for(user, case)
    if p.started_at is None:
        p.started_at = timezone.now()
        p.save(update_fields=["started_at"])
    return p


def elapsed_seconds(p):
    if p.finished_at and p.started_at:
        return min(MAX_SECONDS, int((p.finished_at - p.started_at).total_seconds()))
    if p.started_at:
        return min(MAX_SECONDS, int((timezone.now() - p.started_at).total_seconds()))
    return 0


def hints_released(user, case):
    return HintUsage.objects.filter(user=user, hint__case=case).count()


def next_hint(user, case):
    used = set(HintUsage.objects.filter(user=user, hint__case=case).values_list("hint_id", flat=True))
    return Hint.objects.filter(case=case).exclude(id__in=used).order_by("order").first()


def release_hint(user, case):
    h = next_hint(user, case)
    if h is None:
        return None
    HintUsage.objects.get_or_create(user=user, hint=h)
    p = progress_for(user, case)
    p.hints_used = hints_released(user, case)
    p.save(update_fields=["hints_used"])
    return h


def compute_score(base, hints, attempts, seconds):
    minutes = seconds / 60.0
    time_pen = int(min(TIME_PENALTY_CAP, max(0, minutes - TIME_FREE_MINUTES) * TIME_PENALTY_PER_MIN))
    hint_pen = HINT_PENALTY * hints
    att_pen = ATTEMPT_PENALTY * max(0, attempts - 1)
    return max(0, base - hint_pen - att_pen - time_pen), hint_pen, att_pen, time_pen


def submit_deduction(user, case, data):
    """Server-side evaluation against the protected key. Returns (FinalDeduction, evaluation dict)."""
    p = start_case(user, case)
    sol = CaseSolution.objects.get(case=case).data
    suspects = list(case.suspects.all())
    try:
        embedder = _embedder(case)
    except Exception:
        embedder = None
    ev = answer_eval.evaluate(sol, suspects, data, embedder)
    p.attempts += 1
    if ev["solved"] and not p.solved:
        p.solved = True
        p.finished_at = timezone.now()
        p.seconds_spent = elapsed_seconds(p)
    p.save()
    points = 0
    if ev["solved"]:
        points, hp, ap, tp = compute_score(ev["base_points"], p.hints_used, p.attempts, p.seconds_spent or elapsed_seconds(p))
        s, _ = Score.objects.get_or_create(user=user, case=case)
        if (not s.solved) or points > s.points:
            s.points, s.base_points, s.hint_penalty, s.attempt_penalty, s.time_penalty = points, ev["base_points"], hp, ap, tp
            s.time_taken, s.hints_used, s.solved = p.seconds_spent, p.hints_used, True
            s.save()
    fd = FinalDeduction.objects.create(
        user=user, case=case, attempt_no=p.attempts, culprit_key=data.get("culprit", ""), what_choice=data.get("what", ""),
        when_choice=data.get("when", ""), insight_choice=data.get("insight", ""), evidence_keys=data.get("evidence", []),
        explanation=data.get("explanation", ""), evaluation=ev, correct=ev["solved"], points=points)
    return fd, ev


def _embedder(case):
    from rag_engine.retriever import get_retriever
    return get_retriever(case.number).embedder


def reveal_case(user, case):
    """Give up: unlocks the next case but scores zero."""
    p = progress_for(user, case)
    if p.finished_at is None:
        p.finished_at = timezone.now()
        p.seconds_spent = elapsed_seconds(p)
        p.save()
        s, _ = Score.objects.get_or_create(user=user, case=case)
        s.time_taken, s.hints_used = p.seconds_spent, p.hints_used
        s.save()
    return p


def can_view_results(user, case):
    return PlayerProgress.objects.filter(user=user, case=case, finished_at__isnull=False).exists()


def case_cards(user):
    cards = []
    scores = {s.case_id: s for s in Score.objects.filter(user=user)}
    progs = {p.case_id: p for p in PlayerProgress.objects.filter(user=user)}
    for c in Case.objects.all():
        pr, sc = progs.get(c.id), scores.get(c.id)
        unlocked = is_unlocked(user, c)
        state = "locked"
        if unlocked:
            state = "solved" if pr and pr.solved else "revealed" if pr and pr.finished_at else \
                "in_progress" if pr and pr.started_at else "available"
        cards.append({"case": c, "unlocked": unlocked, "state": state, "points": sc.points if sc else 0})
    return cards


RANKS = [(0, "Baker Street Irregular"), (1, "Consulting Apprentice"), (3, "Inspector's Equal"), (5, "Scotland Yard Consultant"),
         (7, "Detective Master")]


def player_summary(user):
    scores = list(Score.objects.filter(user=user, solved=True))
    solved = len(scores)
    total = sum(s.points for s in scores)
    avg_t = int(sum(s.time_taken for s in scores) / solved) if solved else 0
    hints = sum(s.hints_used for s in scores)
    title = [t for n, t in RANKS if solved >= n][-1]
    best = max(scores, key=lambda s: s.points) if scores else None
    return {"solved": solved, "total": total, "avg_time": avg_t, "hints": hints, "title": title,
            "master": solved >= Case.objects.count() > 0, "max_possible": 1000 * Case.objects.count(),
            "best": best, "scores": sorted(scores, key=lambda s: s.case.number)}


def performance_text(summary):
    if not summary["solved"]:
        return "Your casebook is still empty. Begin with the Missing Emerald."
    pct = summary["total"] / max(1, summary["max_possible"])
    if summary["master"] and pct > 0.75:
        return "A masterly performance: you read the evidence the way Holmes himself would."
    if pct > 0.5:
        return "A capable and methodical detective, who needs only a little more speed and fewer hints."
    return "A promising start. Re-read your notes: cross-checking documents is the habit of great detectives."
