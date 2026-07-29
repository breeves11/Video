"""Business FAQ / knowledge base: CRUD plus a lightweight keyword-overlap
retriever used to ground both the email and phone agents' answers.

No embeddings/vector DB dependency -- for the handful-to-low-hundreds of FAQ
entries a small business actually has, TF-ish keyword overlap is plenty
accurate and keeps the app runnable with zero external services.
"""

import re
from typing import Optional

from . import db

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "i", "you", "we", "they", "he", "she", "it", "my", "your", "our",
    "to", "of", "in", "on", "at", "for", "and", "or", "but", "with",
    "what", "when", "where", "how", "can", "could", "would", "should",
    "please", "thanks", "thank", "hi", "hello", "hey", "there", "this",
    "that", "have", "has", "had", "be", "will", "about", "if",
}


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def add_entry(question: str, answer: str, category: str = "general") -> int:
    with db.session() as conn:
        now = db.now_iso()
        cursor = conn.execute(
            "INSERT INTO kb_entries (question, answer, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (question.strip(), answer.strip(), category.strip() or "general", now, now),
        )
        return cursor.lastrowid


def update_entry(entry_id: int, question: Optional[str] = None, answer: Optional[str] = None,
                  category: Optional[str] = None) -> bool:
    fields, values = [], []
    if question is not None:
        fields.append("question = ?")
        values.append(question.strip())
    if answer is not None:
        fields.append("answer = ?")
        values.append(answer.strip())
    if category is not None:
        fields.append("category = ?")
        values.append(category.strip() or "general")
    if not fields:
        return False
    fields.append("updated_at = ?")
    values.append(db.now_iso())
    values.append(entry_id)
    with db.session() as conn:
        cursor = conn.execute(f"UPDATE kb_entries SET {', '.join(fields)} WHERE id = ?", values)
        return cursor.rowcount > 0


def delete_entry(entry_id: int) -> bool:
    with db.session() as conn:
        cursor = conn.execute("DELETE FROM kb_entries WHERE id = ?", (entry_id,))
        return cursor.rowcount > 0


def list_entries(category: Optional[str] = None) -> list:
    with db.session() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM kb_entries WHERE category = ? ORDER BY id", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM kb_entries ORDER BY id").fetchall()
        return [dict(row) for row in rows]


def search(query: str, limit: int = 3) -> list:
    """Return up to `limit` KB entries most relevant to `query`, ranked by
    token overlap against the entry's question (weighted higher) and answer.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    entries = list_entries()
    scored = []
    for entry in entries:
        question_tokens = _tokenize(entry["question"])
        answer_tokens = _tokenize(entry["answer"])
        score = 2 * len(query_tokens & question_tokens) + len(query_tokens & answer_tokens)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[:limit]]


def format_context(entries: list) -> str:
    if not entries:
        return ""
    lines = [f"Q: {e['question']}\nA: {e['answer']}" for e in entries]
    return "\n\n".join(lines)
