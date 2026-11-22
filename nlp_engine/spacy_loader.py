"""Lazy spaCy loader. Falls back to a blank English pipeline with a sentencizer if the model is missing."""
import logging
from functools import lru_cache
from django.conf import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_nlp():
    import spacy
    name = settings.MYSTIQ["SPACY_MODEL"]
    try:
        nlp = spacy.load(name)
        nlp.meta["mystiq_model"] = name
    except Exception as exc:  # model not installed
        log.warning("spaCy model %s unavailable (%s); using blank pipeline", name, exc)
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        nlp.meta["mystiq_model"] = "blank-en (no pretrained NER/lemmatiser)"
    return nlp


def model_name():
    return get_nlp().meta.get("mystiq_model", "unknown")
