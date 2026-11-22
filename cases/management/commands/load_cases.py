from django.core.management.base import BaseCommand
from cases.loader import load_all


class Command(BaseCommand):
    help = "Load/refresh the seven MYSTIQ cases from data/cases/*.yaml and rebuild NLP-derived timelines."

    def handle(self, *args, **opts):
        cases = load_all()
        for c in cases:
            self.stdout.write(self.style.SUCCESS(
                f"Case {c.number}: {c.title} — {c.suspects.count()} suspects, {c.documents.count()} documents, "
                f"{c.statements.count()} statements, {c.timeline.count()} timeline events"))
