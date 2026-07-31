"""A per-customer view derived from the emails and calls tables, rather than
a separately maintained contacts table -- email/phone are already the
natural identity keys on those rows, so a JOIN-free aggregation in Python
gives the same "everything from this customer" view without a second
record of the same relationship to keep in sync.
"""

from . import db


def list_contacts(limit: int = 100) -> list:
    with db.session() as conn:
        email_rows = conn.execute(
            "SELECT contact_email AS identity, contact_name AS name, status, category, "
            "created_at FROM emails"
        ).fetchall()
        call_rows = conn.execute(
            "SELECT from_number AS identity, status, category, callback_requested, created_at "
            "FROM calls"
        ).fetchall()

    people = {}

    for row in email_rows:
        identity = row["identity"]
        if not identity:
            continue
        person = people.setdefault(identity, _new_person(identity))
        if row["name"] and not person["name"]:
            person["name"] = row["name"]
        person["channels"].add("email")
        person["interactions"] += 1
        if row["status"] == "pending":
            person["open_items"] += 1
        _bump_last_contact(person, row["created_at"])

    for row in call_rows:
        identity = row["identity"]
        if not identity or identity == "unknown":
            continue
        person = people.setdefault(identity, _new_person(identity))
        person["channels"].add("phone")
        person["interactions"] += 1
        if row["callback_requested"]:
            person["open_items"] += 1
        _bump_last_contact(person, row["created_at"])

    results = sorted(people.values(), key=lambda p: p["last_contact_at"] or "", reverse=True)
    for person in results:
        person["channels"] = sorted(person["channels"])
    return results[:limit]


def _new_person(identity: str) -> dict:
    return {
        "identity": identity,
        "name": None,
        "channels": set(),
        "interactions": 0,
        "open_items": 0,
        "last_contact_at": None,
    }


def _bump_last_contact(person: dict, created_at: str) -> None:
    if created_at and (person["last_contact_at"] is None or created_at > person["last_contact_at"]):
        person["last_contact_at"] = created_at
