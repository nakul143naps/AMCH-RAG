import httpx
import json

api = "http://localhost:8000"

def test_q(name, payload):
    print(f"=== {name} ===")
    r = httpx.post(f"{api}/query", json=payload, timeout=60)
    data = r.json()
    print("Status:", r.status_code)
    print("Provider:", data.get("provider_used"))
    cits = data.get("citations", [])
    print("Citations count:", len(cits))
    for c in cits:
        print(f"  [{c.get('index')}] {c.get('source')} (chunk: {c.get('chunk_id')})")
    answer = data.get("answer", "")[:250].encode("ascii", errors="replace").decode()
    print("Answer preview:", answer)
    print()

def main():
    test_q("1. GREETING (hii)", {"query": "hii", "session_id": "s_greet"})
    test_q("2. GENERAL KNOWLEDGE (photosynthesis)", {"query": "What is photosynthesis?", "session_id": "s_gen"})
    test_q("3. INTERNAL DOC (9 clusters roadmap)", {"query": "What are the 9 clusters mentioned in the roadmap?", "session_id": "s_doc1"})
    test_q("4. REPEATED QUERY (9 clusters roadmap)", {"query": "What are the 9 clusters mentioned in the roadmap?", "session_id": "s_doc1"})
    test_q("5. INTERNAL DOC (transfer learning)", {"query": "What is transfer learning?", "session_id": "s_doc2"})
    test_q("6. MEMORY TURN 1", {"query": "My favorite machine learning library is PyTorch", "session_id": "s_mem", "user_id": "u1"})
    test_q("7. MEMORY TURN 2", {"query": "What is my favorite machine learning library?", "session_id": "s_mem", "user_id": "u1"})
    test_q("8. ACCESS HIERARCHY (admin access)", {"query": "What are the 9 clusters mentioned in the roadmap?", "session_id": "s_admin", "access_level": "admin"})

if __name__ == "__main__":
    main()
