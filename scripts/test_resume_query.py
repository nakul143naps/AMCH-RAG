import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.graph import build_agent_graph

async def main():
    graph = build_agent_graph()
    queries = [
        "what is the name of the person whose resume i just shared",
        "what are the skills from the document i uploaded",
        "summarize the uploaded document",
    ]
    for q in queries:
        print(f"\n==========================================")
        print(f"QUERY: {q}")
        print(f"==========================================")
        res = await graph.ainvoke({
            "query": q,
            "chat_history": [],
            "access_level": "default",
        })
        print(f"ROUTE: {res.get('route')}")
        print(f"RETRIEVED CHUNKS: {len(res.get('retrieved_docs', []))}")
        print(f"ANSWER:\n{res.get('final_answer')}")
        print(f"CITATIONS:\n{res.get('citations')}")

if __name__ == "__main__":
    asyncio.run(main())
