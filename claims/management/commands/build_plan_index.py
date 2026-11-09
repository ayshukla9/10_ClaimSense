"""A9: download the embedding model and build the plan-document index ahead of time.

    python manage.py build_plan_index            # embeddings index only (~90 MB download once)
    python manage.py build_plan_index --llm      # also download/load the local LLM (~3 GB once)

Optional: the app does both lazily on first use. Running this before a demo avoids the wait.
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from claims.ai import local_llm, retrieval


class Command(BaseCommand):
    help = "Pre-download the A9 models and build the retrieval index."

    def add_arguments(self, parser):
        parser.add_argument("--llm", action="store_true", help="Also load the local LLM.")

    def handle(self, *args, **opts):
        start = time.perf_counter()
        try:
            chunks, dims = retrieval.build_index()
        except retrieval.RetrievalUnavailable as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f"Indexed {chunks} chunks with {settings.EMBEDDING_MODEL} ({dims} dims) in "
            f"{time.perf_counter() - start:.1f} s; saved under {settings.RAG_INDEX_DIR}"))
        if opts["llm"]:
            start = time.perf_counter()
            try:
                local_llm.get_pipeline()
            except local_llm.LocalModelUnavailable as exc:
                raise CommandError(str(exc))
            self.stdout.write(self.style.SUCCESS(
                f"Loaded {settings.LOCAL_LLM_MODEL} in {time.perf_counter() - start:.1f} s"))
