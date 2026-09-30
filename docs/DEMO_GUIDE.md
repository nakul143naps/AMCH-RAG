# AMCH-RAG Interview Demo

Use this short walkthrough to show the project’s actual end-to-end behavior without uploading anyone’s private documents.

## Before the interview

1. Confirm the AWS demo URL opens and `/health` responds.
2. Upload [`../examples/demo_company_handbook.md`](../examples/demo_company_handbook.md) to the chat.
3. Wait for the upload status to say it finished indexing.
4. Use a fresh chat session for a clean walkthrough.

The sample handbook is fictional and safe to use in a public demo. Do not upload personal resumes, API keys, customer files, or other sensitive documents to the shared EC2 instance.

## Five-minute walkthrough

1. **Explain the problem:** keyword-only search misses paraphrases, while a plain LLM can invent details absent from a file.
2. **Show ingestion:** upload the handbook and point out the asynchronous job status.
3. **Show grounded retrieval:** ask “What is the remote-work allowance?” Confirm the answer cites `demo_company_handbook.md`.
4. **Show a second section:** ask “How many days do employees have to submit expenses?” Confirm the answer is grounded in the expense policy.
5. **Show multi-part retrieval:** ask “Summarize the leave and onboarding policies.” Check that the response uses the appropriate passages and citations.
6. **Explain correction:** describe how weak results can be graded, rewritten, and retrieved again; web fallback is optional and must be identified as external.
7. **Show observability:** open `/health`, then describe the architecture using [the C4-inspired diagrams](ARCHITECTURE.md).

## Questions with known answers

| Ask | Expected fact | What to verify |
|---|---|---|
| What is the remote-work allowance? | Up to 2 remote days per week, with manager approval | Citation points to the handbook |
| How many days do employees have to submit expenses? | Within 10 calendar days after the expense | Citation points to the expenses section |
| How much paid annual leave is provided? | 20 working days per calendar year | Citation points to the leave section |
| What is the onboarding buddy’s role? | Help with tools, team introductions, and first-month questions | Answer should not invent additional duties |

Exact phrasing may vary by model provider. Judge the demo by whether the facts and source citations are correct, not whether the generated sentence is identical.

## If the demo does not answer

- Confirm the document upload completed successfully; an accepted upload is not necessarily an indexed upload.
- Check `/health` and the document catalog.
- Rephrase the question using terms from the handbook.
- Avoid repeated rapid requests if the model provider is rate-limited.
- Do not present a web-sourced fallback as an answer grounded in the uploaded document.

## 30-second project summary

> AMCH-RAG is a full-stack document Q&A system. It ingests files, indexes them with local dense and BM25 embeddings in Qdrant, fuses and reranks retrieval results, and uses a LangGraph workflow to grade relevance, retry weak searches, and verify generated answers before returning source citations. The demo runs as a small AWS EC2 deployment; the repository documents the reliability and security trade-offs rather than claiming high availability.
