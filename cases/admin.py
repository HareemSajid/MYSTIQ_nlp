from django.contrib import admin
from .models import Case, EvidenceDocument, Hint, Statement, Suspect, TimelineEvent

for m in (Case, Suspect, EvidenceDocument, Statement, TimelineEvent, Hint):
    admin.site.register(m)
# CaseSolution is deliberately NOT registered in the admin.
