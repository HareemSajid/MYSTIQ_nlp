from django.core.management.base import BaseCommand
from rag_engine.indexer import build_all


class Command(BaseCommand):
    help = "Chunk every case, embed the chunks and build the per-case FAISS vector indexes (vector_store/)."

    def add_arguments(self, parser):
        parser.add_argument("--local", action="store_true", help="force the offline local embedder")

    def handle(self, *a, **o):
        r = build_all(force_local=o["local"], verbose=self.stdout.write)
        self.stdout.write(self.style.SUCCESS(f"Built indexes with {r['embedder']}"))
