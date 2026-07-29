from backend import knowledge_base


def test_add_list_update_delete_entry():
    entry_id = knowledge_base.add_entry("What are your hours?", "Mon-Fri 9-5", "general")
    entries = knowledge_base.list_entries()
    assert len(entries) == 1
    assert entries[0]["id"] == entry_id

    assert knowledge_base.update_entry(entry_id, answer="Mon-Sat 9-6")
    updated = knowledge_base.list_entries()[0]
    assert updated["answer"] == "Mon-Sat 9-6"

    assert knowledge_base.delete_entry(entry_id)
    assert knowledge_base.list_entries() == []


def test_search_ranks_best_match_first():
    knowledge_base.add_entry("What are your business hours?", "We are open 9am-5pm Mon-Fri.")
    knowledge_base.add_entry("Do you offer refunds?", "Yes, within 30 days of purchase.")

    results = knowledge_base.search("What time do you open on Saturday?")
    assert results
    assert "hours" in results[0]["question"].lower()


def test_search_returns_empty_for_unrelated_query():
    knowledge_base.add_entry("Do you ship internationally?", "Yes, to most countries.")
    results = knowledge_base.search("xyzabc123 nonsense query")
    assert results == []


def test_search_respects_limit():
    for i in range(5):
        knowledge_base.add_entry(f"question about pricing {i}", "pricing answer", "pricing")
    results = knowledge_base.search("pricing question", limit=2)
    assert len(results) == 2
