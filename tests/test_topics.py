"""Offline tests for the knowledge topic classifier (pure heuristic — no DB/network)."""

from collector.seed_knowledge import seed_documents
from collector.topics import CRAFT, FARM, classify_topic, topic_for_question


def test_strong_craft_signal_tags_craft():
    # A single strong term (orb / essence / omen / craft verb) is enough.
    assert classify_topic("Essence crafting guide", "Use a Greater Essence on the base.") == CRAFT
    assert classify_topic("", "Omen of Whittling removes the lowest-level modifier.") == CRAFT
    assert classify_topic("", "Slam an Exalted Orb to add a mod.") == CRAFT


def test_weak_terms_need_a_pair():
    # One weak term alone stays farm; two tip it into craft.
    assert classify_topic("", "Watch your item level when mapping.") == FARM
    assert classify_topic("", "Roll a good prefix and suffix on the base.") == CRAFT


def test_farm_content_is_not_craft():
    farm = (
        "Best currency farm in PoE2: run breach maps with an atlas tree focused on "
        "tablet towers for divine drops. Clear fast and rotate maps."
    )
    assert classify_topic("PoE2 atlas farming strategy", farm) == FARM


def test_word_boundary_avoids_false_positives():
    # 'Warcraft' must not trip the 'craft' term.
    assert classify_topic("World of Warcraft", "Just a passing mention, nothing about PoE.") == FARM


def test_all_seed_docs_classify_as_craft():
    for d in seed_documents():
        assert classify_topic(d.title, d.content) == CRAFT


def test_topic_for_question_narrows_only_for_craft():
    assert topic_for_question("What omen do I use to craft a bow?") == CRAFT
    assert topic_for_question("Which essence guarantees life?") == CRAFT
    # Farm/general questions stay broad (no filter) so they aren't starved.
    assert topic_for_question("What is the best currency farm right now?") is None
    assert topic_for_question("Where do I level fastest in act 2?") is None
