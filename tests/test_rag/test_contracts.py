"""Tests for pycommon.rag.contracts."""

import pytest

from pycommon.rag import contracts


def test_nova_model_id_is_the_one_pipeline_model():
    """The model id is a fixed constant of the pipeline."""
    assert contracts.NOVA_EMBEDDING_MODEL_ID == (
        "amazon.nova-2-multimodal-embeddings-v1:0"
    )


def test_normalize_source_id_strips_only_the_protocol():
    """Only a protocol prefix and surrounding spaces are removed."""
    assert (
        contracts.normalize_source_id(" s3://global2/a.content.json ")
        == "global2/a.content.json"
    )
    assert contracts.normalize_source_id("global/a.json") == "global/a.json"


def test_normalize_source_id_rejects_non_strings():
    """A non-string id is a programming error."""
    with pytest.raises(TypeError, match="must be a string"):
        contracts.normalize_source_id(None)


def test_namespace_defaults_unknown_ids_to_legacy():
    """Only global2 ids are in the new namespace."""
    ns = contracts.EmbeddingNamespace
    assert contracts.namespace_for_source("s3://global2/x.json") is ns.GLOBAL2
    assert contracts.namespace_for_source("global2") is ns.GLOBAL2
    assert contracts.namespace_for_source("global/x.json") is ns.GLOBAL
    assert contracts.namespace_for_source("user-file-id") is ns.GLOBAL


def test_generation_fingerprint_is_stable_and_changes_with_model():
    """Same inputs give the same fingerprint, a different model does not."""
    args = {"content_hash": "abc", "source_version": "1", "model_id": "nova"}
    first = contracts.generation_fingerprint(embedding_dimension=1024, **args)
    same = contracts.generation_fingerprint(embedding_dimension=1024, **args)
    changed = contracts.generation_fingerprint(embedding_dimension=3072, **args)
    assert first == same
    assert first != changed


def test_page_id_is_deterministic_and_validates_the_page():
    """A page id names the document, page and optional generation."""
    assert contracts.page_id("s3://global2/d.json", 2) == "global2/d.json:page:2"
    assert (
        contracts.page_id("global2/d.json", 2, "g1")
        == "global2/d.json:page:2:generation:g1"
    )
    with pytest.raises(ValueError, match="page_number"):
        contracts.page_id("global2/d.json", 0)


def test_page_qa_input_retains_page_local_text_and_provenance():
    """The QA input carries the page text and where it came from."""
    page = contracts.build_page_input(
        "s3://global2/doc.content.json",
        2,
        text="Only page two",
        text_location="global2/doc/pages/2.json",
        image_location="global2/doc/pages/2.png",
        extraction_method="textract",
        generation_id="generation-1",
        locations=[{"page_number": 2, "bbox": [0, 0, 1, 1]}],
    )
    qa_input = page.qa_input()
    assert qa_input["source_id"] == "global2/doc.content.json"
    assert qa_input["page_number"] == 2
    assert qa_input["text"] == "Only page two"
    assert qa_input["image_location"].endswith("/2.png")
    assert qa_input["locations"] == [{"page_number": 2, "bbox": [0, 0, 1, 1]}]
    assert qa_input["page_id"] == page.id
    assert "page:2" in page.id


def test_build_page_input_defaults_to_no_locations():
    """A page with no location data has an empty tuple of locations."""
    page = contracts.build_page_input("global2/doc.json", 1)
    assert page.locations == ()
    assert page.qa_input()["locations"] == []
