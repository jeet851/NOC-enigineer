"""
Persistent Conversation Memory Manager – Phase 3 Intelligence Enhancement
Implements DB-backed per-operator conversation memory using the existing ChatHistory
model. Replaces in-memory chat_sessions dict in routes/chat.py so memory survives
server restarts and can be searched for previous discussions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.memory_manager")

# Maximum turns stored in the DB per session
MAX_DB_TURNS = 100
# Maximum turns passed into active LLM context window
MAX_CONTEXT_TURNS = 20


class MemoryManager:
    """
    Persistent, DB-backed conversation memory with cross-session topic search.
    Gracefully falls back to an in-memory dict if the DB is unavailable.
    """

    # ------------------------------------------------------------------
    # In-memory fallback store (also used as write-through cache)
    # ------------------------------------------------------------------
    _cache: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def append_message(
        session_id: str,
        role: str,
        content: str,
        persona: Optional[str] = None,
        db=None,
    ) -> None:
        """
        Append a single message to the session. Writes to DB and updates cache.

        Parameters
        ----------
        session_id : str   – unique session identifier (e.g. username + '-' + tab)
        role       : str   – 'user' | 'model'
        content    : str   – message text
        persona    : str   – persona key (optional)
        db                 – SQLAlchemy Session (optional)
        """
        msg = {
            "role": role,
            "text": content,
            "persona": persona,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 1. Update in-memory cache
        if session_id not in MemoryManager._cache:
            MemoryManager._cache[session_id] = []
        MemoryManager._cache[session_id].append(msg)
        # Trim cache to MAX_CONTEXT_TURNS
        MemoryManager._cache[session_id] = MemoryManager._cache[session_id][
            -MAX_CONTEXT_TURNS:
        ]

        # 2. Persist to DB
        if db is not None:
            try:
                from models.chat_history import ChatHistory

                row = ChatHistory(
                    session_id=session_id,
                    role=role,
                    content=content,
                    persona=persona,
                    timestamp=datetime.utcnow(),
                )
                db.add(row)
                db.commit()
            except Exception as e:
                logger.warning(f"Memory DB write failed for session {session_id}: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Read – active context window
    # ------------------------------------------------------------------

    @staticmethod
    def get_history(session_id: str, db=None, limit: int = MAX_CONTEXT_TURNS) -> List[Dict]:
        """
        Return the last `limit` messages for the session.
        Loads from DB on first access (cache miss), then serves from cache.
        """
        # Cache hit
        if session_id in MemoryManager._cache and MemoryManager._cache[session_id]:
            return MemoryManager._cache[session_id][-limit:]

        # Cache miss → load from DB
        if db is not None:
            try:
                from models.chat_history import ChatHistory

                rows = (
                    db.query(ChatHistory)
                    .filter(ChatHistory.session_id == session_id)
                    .order_by(ChatHistory.timestamp.desc())
                    .limit(MAX_DB_TURNS)
                    .all()
                )
                history = [
                    {
                        "role": r.role,
                        "text": r.content,
                        "persona": r.persona,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    }
                    for r in reversed(rows)
                ]
                MemoryManager._cache[session_id] = history
                return history[-limit:]
            except Exception as e:
                logger.warning(f"Memory DB read failed for session {session_id}: {e}")

        return []

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    @staticmethod
    def clear_session(session_id: str, db=None) -> None:
        """Clear all messages for a session from cache and DB."""
        MemoryManager._cache.pop(session_id, None)
        if db is not None:
            try:
                from models.chat_history import ChatHistory

                db.query(ChatHistory).filter(
                    ChatHistory.session_id == session_id
                ).delete()
                db.commit()
            except Exception as e:
                logger.warning(f"Memory DB clear failed: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Cross-session search (for follow-up questions like "the VPN issue")
    # ------------------------------------------------------------------

    @staticmethod
    def search_memory(
        session_id: str,
        query: str,
        db=None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Search previous messages in this session that mention a topic.
        Used to enrich follow-up questions with relevant prior context.

        Returns up to `limit` matching messages (most recent first).
        """
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        if not keywords:
            return []

        candidates: List[Dict] = []

        # 1. Search in-memory cache first
        history = MemoryManager._cache.get(session_id, [])
        for msg in reversed(history):
            text = msg.get("text", "").lower()
            if any(kw in text for kw in keywords):
                candidates.append(msg)
                if len(candidates) >= limit:
                    return candidates

        # 2. Search DB if not enough found in cache
        if db is not None and len(candidates) < limit:
            try:
                from models.chat_history import ChatHistory
                from sqlalchemy import or_

                clauses = [
                    ChatHistory.content.ilike(f"%{kw}%") for kw in keywords
                ]
                rows = (
                    db.query(ChatHistory)
                    .filter(ChatHistory.session_id == session_id)
                    .filter(or_(*clauses))
                    .order_by(ChatHistory.timestamp.desc())
                    .limit(limit)
                    .all()
                )
                for r in rows:
                    candidate = {
                        "role": r.role,
                        "text": r.content,
                        "persona": r.persona,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    }
                    if candidate not in candidates:
                        candidates.append(candidate)
            except Exception as e:
                logger.warning(f"Memory search DB query failed: {e}")

        return candidates[:limit]

    # ------------------------------------------------------------------
    # Memory context injection for LLM
    # ------------------------------------------------------------------

    @staticmethod
    def build_memory_context(
        session_id: str,
        current_query: str,
        db=None,
    ) -> str:
        """
        Build a memory context string to inject into the system prompt when
        relevant prior discussions are found. Enables follow-up resolution
        like "The VPN issue happened again."
        """
        matches = MemoryManager.search_memory(session_id, current_query, db=db)
        if not matches:
            return ""

        lines = ["RELEVANT PRIOR CONVERSATION (from memory):"]
        for msg in matches[:3]:
            role_label = "Operator" if msg.get("role") == "user" else "AI Copilot"
            text = msg.get("text", "")[:200]
            ts = msg.get("timestamp", "")[:16] if msg.get("timestamp") else ""
            lines.append(f"  [{ts}] {role_label}: {text}")
        lines.append(
            "(Use this prior context to answer follow-up questions "
            "without asking the operator to repeat details.)"
        )
        return "\n".join(lines)
