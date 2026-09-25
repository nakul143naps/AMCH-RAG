"""Router node for LangGraph orchestrator deciding query execution path."""

import logging
import re
from typing import Any

from app.agent.state import AgentState, RouteType
from app.cache.service import TwoTierCacheService
from app.gateway.client import ModelGateway
from app.retrieval.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_INSTRUCTION = """You are an intelligent Self-RAG routing agent deciding whether document retrieval is actually necessary.
Analyze the user query, the conversation context, and the list of available uploaded documents and their summarized topics.
Decide the optimal execution route:

- "direct": Strictly for general world knowledge, math calculations, code templates, or topics completely unrelated to any uploaded documents (e.g. "what is photosynthesis", "capital of Italy", "solve 2x + 5 = 15", "write a hello world in C"). Use direct ONLY when the user's question has zero overlap with any uploaded documents.
- "retrieve": Questions asking for information from uploaded files, or questions related to ANY topic, section, cluster, roadmap, concept, algorithm, or methodology present in the uploaded document summaries below.
- "cache": Any greeting, salutation, or chit-chat (e.g. "hi", "hello", "hey", "how are you", "who are you").
- "memory": Questions answerable purely from known user profile facts or previous conversation history (e.g. "what did I ask earlier", "what is my name").

CRITICAL SELF-RAG RULES:
1. Examine the summaries, topics, and titles of the injected internal documents below. If the user's question touches upon, asks about, or can be answered by any topic, section, cluster, roadmap, concept, or terminology present in the uploaded document summaries, ALWAYS choose "retrieve".
2. If in doubt whether a topic is covered in the uploaded documents, choose "retrieve" to ensure the answer is grounded in internal documents rather than generic LLM pre-training.
3. Choose "direct" ONLY for universal world knowledge (e.g. "what is photosynthesis", "capital of Italy", "math problems") that has zero connection to the uploaded documents.
4. NEVER choose "retrieve" for simple conversational greetings or chit-chat.

Respond with your decision in the exact format:
ROUTE: <direct|retrieve|cache|memory>
REASON: <one sentence justification>"""

GREETING_PATTERNS = [
    r"^h+i+\b",
    r"^h+e+y+\b",
    r"^h+e+l+l+o+\b",
    r"^(howdy|greetings|hiya|hola|namaste|aloha)\b",
    r"^(yo|sup|wassup|what'?s\s+up)\b",
    r"^good\s+(morning|afternoon|evening|night|day)\b",
    r"^(thank\s*you|thanks|thx|cheers|ty)\b",
    r"^(who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|help(\s+me)?)\b",
    r"^how\s+(are\s+you|are\s+things|is\s+it\s+going|do\s+you\s+do)\b",
]

MEMORY_PATTERNS = [
    r"what\s+(was|were)\s+(my|the)\s+(first|last|previous|earlier)\s+question",
    r"what\s+did\s+i\s+(just\s+)?(ask|say|tell|mention)",
    r"who\s+am\s+i\b",
    r"what\s+is\s+my\s+[a-z0-9_ ]+",
    r"\b(my\s+favorite|my\s+preference|about\s+me|remember\s+about\s+me)\b",
    r"\bdo\s+you\s+remember\b",
    r"what\s+did\s+we\s+(talk|discuss)\s+about",
    r"repeat\s+what\s+(i|you)\s+said",
    r"summarize\s+(our|the)\s+(chat|conversation)",
]


class RouterNode:
    """Evaluates the user query to choose the optimal downstream node using cached summaries."""

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        cache_service: TwoTierCacheService | None = None,
        vector_mgr: VectorStoreManager | None = None,
    ) -> None:
        self.gateway = gateway or ModelGateway.get_instance()
        self.cache_service = cache_service or TwoTierCacheService.get_instance()
        self.vector_mgr = vector_mgr or VectorStoreManager.get_instance()

    def _is_conversational_greeting(self, query: str) -> bool:
        """Check if query is a pure conversational greeting or chit-chat."""
        normalized = query.strip().lower()
        if len(normalized) <= 2:
            return True
        for pattern in GREETING_PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    def _is_memory_query(self, query: str) -> bool:
        """Check if query specifically asks about past turns or user identity."""
        normalized = query.strip().lower()
        for pattern in MEMORY_PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Classify user query and set route in AgentState."""
        query = state.get("query", "").strip()
        access_level = state.get("access_level", "default")

        # 1. Fast-path for greetings / pleasantries to save latency & tokens
        if self._is_conversational_greeting(query):
            logger.info(
                f"Router fast-path matched greeting for: '{query}' -> route=cache"
            )
            return {"route": "cache"}

        # 2. Fast-path for conversational memory / dialogue history questions
        if self._is_memory_query(query):
            logger.info(
                f"Router matched conversational memory pattern for: '{query}' -> route=memory"
            )
            return {"route": "memory"}

        # 3. Two-Tier Cache Lookup for repeated questions (<10ms)
        try:
            cached_entry, hit_type = await self.cache_service.async_lookup(
                query=query, access_level=access_level
            )
            if cached_entry:
                logger.info(
                    f"Router found verified cached answer ({hit_type}) for repeated query: '{query}' -> route=cache"
                )
                return {"route": "cache"}
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Router cache probe check: {e}")

        # 4. Load high-level document summaries from SQLite cache
        cached_summaries = self.cache_service.cache_mgr.get_all_document_summaries()
        doc_catalog_text = "No internal documents currently uploaded in knowledge base."
        all_topics_set: set[str] = set()

        if cached_summaries:
            doc_lines = []
            for d in cached_summaries:
                name = d.get("source_name", "Untitled")
                summary = d.get("summary", "")
                topics = d.get("topics", "")
                doc_lines.append(
                    f'- Document: "{name}"\n  Topics: {topics}\n  Summary: {summary}'
                )
                for t in topics.split(","):
                    t_clean = t.strip().lower()
                    if len(t_clean) > 3:
                        all_topics_set.add(t_clean)
            doc_catalog_text = "INJECTED INTERNAL DOCUMENTS & TOPICS:\n" + "\n".join(doc_lines)
        else:
            # Fallback to vector store document list if cache empty
            try:
                docs = self.vector_mgr.list_documents()
                if docs:
                    doc_lines = []
                    for d in docs:
                        name = d.get("source_name", "Untitled")
                        summary = d.get("summary", "")
                        count = d.get("chunk_count", 0)
                        doc_lines.append(f'- Document "{name}" ({count} chunks) | Topics: {summary}')
                    doc_catalog_text = "INJECTED INTERNAL DOCUMENTS & TOPICS:\n" + "\n".join(doc_lines)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Router could not list documents: {e}")

        # 5. Programmatic topic overlap fast-path:
        # If query explicitly contains a key topic phrase from the uploaded documents, route to retrieve immediately
        query_lower = query.lower()
        if all_topics_set:
            for topic in all_topics_set:
                if (len(topic) > 4 and topic in query_lower) or (len(query_lower) > 4 and query_lower in topic):
                    logger.info(
                        f"Router fast-path matched document topic '{topic}' in query '{query}' -> route=retrieve"
                    )
                    return {"route": "retrieve"}

        # Prepare router prompt with history context if present
        history_summary = ""
        chat_history = state.get("chat_history", [])
        if chat_history:
            recent_turns = chat_history[-4:]
            history_summary = (
                "Recent Conversation:\n"
                + "\n".join(
                    f"- {getattr(msg, 'type', 'message')}: {getattr(msg, 'content', str(msg))}"
                    for msg in recent_turns
                )
                + "\n\n"
            )

        prompt = (
            f"{doc_catalog_text}\n\n"
            f"{history_summary}"
            f"User Query: {query}\n\n"
            "Determine the route (direct, retrieve, memory, cache):"
        )

        try:
            response_text, provider = await self.gateway.generate(
                prompt=prompt,
                purpose="routing",
                system_instruction=ROUTER_SYSTEM_INSTRUCTION,
                temperature=0.0,
            )
            route = self._parse_route(response_text)
            logger.info(f"Router classified query via {provider} -> route={route}")
            return {"route": route}
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Router LLM classification failed ({e}), falling back to 'retrieve'"
            )
            return {"route": "retrieve"}

    def _parse_route(self, text: str) -> RouteType:
        """Extract route decision from LLM text response."""
        lower = text.lower()
        # Look for explicit format first: ROUTE: <route>
        match = re.search(r"route\s*:\s*(direct|cache|memory|retrieve|tool_call)", lower)
        if match:
            return match.group(1)  # type: ignore[return-value]

        # Keyword scan
        if "direct" in lower or "no_retrieval" in lower:
            return "direct"
        if "cache" in lower:
            return "cache"
        if "memory" in lower:
            return "memory"
        if "tool_call" in lower:
            return "tool_call"
        return "retrieve"
