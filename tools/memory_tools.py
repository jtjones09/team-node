"""CrewAI tool wrappers for memory operations."""

from crewai.tools import tool

from lenses.perspective import PerspectiveLens
from memory.markdown_log import MarkdownLog


def create_memory_tools(lens: PerspectiveLens, logger: MarkdownLog):
    """Create memory tools bound to a specific agent's perspective lens.

    Returns a list of CrewAI tool functions.
    """

    @tool("Store Memory")
    def store_memory(content: str, entry_type: str = "note") -> str:
        """Store information in the shared memory fabric.

        Args:
            content: The information to store.
            entry_type: Type of entry (note, decision, research, task).
        """
        node_id = lens.store(content, {"entry_type": entry_type})
        logger.log(lens.domain, entry_type, f"Stored node {node_id}", content)
        return f"Stored memory node {node_id} in domain '{lens.domain}'."

    @tool("Retrieve Memory")
    def retrieve_memory(query: str, top_k: int = 5) -> str:
        """Search the shared memory fabric for relevant information.

        Args:
            query: What to search for.
            top_k: Max number of results to return.
        """
        results = lens.retrieve(query, top_k=top_k)
        if not results:
            return "No relevant memories found."
        lines = []
        for r in results:
            lines.append(f"[{r['id'][:8]}] (score: {r['score']:.3f}) {r['content'][:200]}")
        return "\n".join(lines)

    @tool("Log Decision")
    def log_decision(title: str, content: str) -> str:
        """Log a decision to the structured markdown log.

        Args:
            title: Short title for the decision.
            content: Full explanation of the decision and rationale.
        """
        path = logger.log(lens.domain, "decision", title, content)
        lens.store(f"DECISION: {title} - {content}", {"entry_type": "decision"})
        return f"Decision logged to {path} and stored in memory."

    return [store_memory, retrieve_memory, log_decision]
