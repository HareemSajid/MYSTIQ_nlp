from django.conf import settings
from django.db import models
from cases.models import Case, EvidenceDocument, Hint, Suspect

User = settings.AUTH_USER_MODEL


class PlayerProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="progress")
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    solved = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    hints_used = models.PositiveSmallIntegerField(default=0)
    important_docs = models.JSONField(default=list)
    notebook = models.TextField(blank=True)
    seconds_spent = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("user", "case")]


class HintUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hint = models.ForeignKey(Hint, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "hint")]


class Interrogation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    suspect = models.ForeignKey(Suspect, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "case", "suspect")]


class InterrogationMessage(models.Model):
    interrogation = models.ForeignKey(Interrogation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10)          # player | suspect
    text = models.TextField()
    mode = models.CharField(max_length=20, blank=True)       # gemini | demo
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class WatsonMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    role = models.CharField(max_length=10)          # player | watson
    kind = models.CharField(max_length=10, default="chat")   # chat | hint | ask
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class FinalDeduction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    attempt_no = models.PositiveSmallIntegerField(default=1)
    culprit_key = models.CharField(max_length=40)
    what_choice = models.CharField(max_length=4)
    when_choice = models.CharField(max_length=4)
    insight_choice = models.CharField(max_length=4)
    evidence_keys = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    evaluation = models.JSONField(default=dict)
    correct = models.BooleanField(default=False)
    points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scores")
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
    base_points = models.IntegerField(default=0)
    hint_penalty = models.IntegerField(default=0)
    attempt_penalty = models.IntegerField(default=0)
    time_penalty = models.IntegerField(default=0)
    time_taken = models.PositiveIntegerField(default=0)
    hints_used = models.PositiveSmallIntegerField(default=0)
    solved = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "case")]


class RetrievedEvidenceLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=20)       # ask | watson | suspect | explain
    query = models.TextField()
    results = models.JSONField(default=list)        # [{chunk_id, doc_key, score, rank}]
    top_k = models.PositiveSmallIntegerField(default=5)
    backend = models.CharField(max_length=60, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["case", "purpose"])]
