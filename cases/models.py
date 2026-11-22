from django.db import models


class Case(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    difficulty = models.CharField(max_length=30)
    setting = models.CharField(max_length=200)
    summary = models.TextField()
    introduction = models.TextField()
    objective = models.TextField()
    places = models.JSONField(default=list)
    case_objects = models.JSONField(default=list)
    others = models.JSONField(default=list)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Case {self.number}: {self.title}"


class CaseSolution(models.Model):
    """Canonical answer key. Server-side only: never serialised, never indexed, never sent to templates/JS."""
    case = models.OneToOneField(Case, on_delete=models.CASCADE, related_name="solution")
    data = models.JSONField()

    def __str__(self):
        return f"Solution for case {self.case.number}"


class Suspect(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="suspects")
    key = models.SlugField(max_length=40)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=160)
    gender = models.CharField(max_length=1, default="m")
    age = models.PositiveSmallIntegerField(default=40)
    aliases = models.JSONField(default=list)
    background = models.TextField()
    motive = models.TextField()
    relationship = models.TextField()
    whereabouts = models.TextField()
    personality = models.TextField()
    private_knowledge = models.TextField()      # persona context, only ever shown to that suspect's AI
    does_not_know = models.TextField(blank=True)
    deflect = models.TextField(blank=True)
    topics = models.JSONField(default=list)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("case", "key")]
        ordering = ["case", "order"]

    def __str__(self):
        return self.name


class EvidenceDocument(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="documents")
    key = models.SlugField(max_length=60)
    title = models.CharField(max_length=200)
    doc_type = models.CharField(max_length=40)
    datetime_text = models.CharField(max_length=120)
    author = models.CharField(max_length=160)
    suspect = models.ForeignKey(Suspect, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    content = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("case", "key")]
        ordering = ["case", "order"]
        indexes = [models.Index(fields=["case", "doc_type"])]

    def __str__(self):
        return self.title


class Statement(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="statements")
    suspect = models.ForeignKey(Suspect, on_delete=models.CASCADE, related_name="statements")
    document = models.ForeignKey(EvidenceDocument, null=True, blank=True, on_delete=models.SET_NULL)
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["case", "order"]
        indexes = [models.Index(fields=["case", "suspect"])]


class TimelineEvent(models.Model):
    """Produced by the temporal-extraction pipeline (nlp_engine.timeline), not hand-written."""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="timeline")
    sort_minutes = models.IntegerField(null=True)      # minutes from midnight; after-midnight events > 1440
    time_label = models.CharField(max_length=40)
    text = models.TextField()
    source = models.ForeignKey(EvidenceDocument, null=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=20, default="record")  # record | claim | other_day
    day_label = models.CharField(max_length=40, blank=True)
    precision = models.CharField(max_length=20, default="exact")
    ambiguous = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["case", "sort_minutes"]


class Hint(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="hints")
    order = models.PositiveSmallIntegerField()
    text = models.TextField()

    class Meta:
        unique_together = [("case", "order")]
        ordering = ["case", "order"]
