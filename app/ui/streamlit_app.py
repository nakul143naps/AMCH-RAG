"""Streamlit Interactive Chat UI for AMCH-RAG with real-time SSE streaming, citations, and feedback."""

import json
import uuid

import httpx
import streamlit as st

st.set_page_config(
    page_title="AMCH-RAG Enterprise Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0px; }
    .sub-header { font-size: 1.0rem; color: #4B5563; margin-bottom: 20px; }
    .citation-box { background-color: #F3F4F6; border-left: 3px solid #3B82F6; padding: 8px 12px; margin: 4px 0; border-radius: 4px; font-size: 0.85rem; }
    .correction-badge { background-color: #FEF3C7; color: #92400E; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; display: inline-block; margin-bottom: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
if "user_id" not in st.session_state:
    st.session_state.user_id = "user_demo"

# Sidebar: Controls & Document Management
with st.sidebar:
    st.title("⚙️ AMCH-RAG Control")
    api_base = st.text_input("API Base URL", value="http://localhost:8000")

    st.subheader("👤 User & Session")
    user_id = st.text_input("User ID", value=st.session_state.user_id)
    session_id = st.text_input("Session ID", value=st.session_state.session_id)
    access_level = st.selectbox("Tenant Access Level", ["default", "public", "confidential", "admin"])

    st.divider()

    st.subheader("📄 Document Ingestion")
    uploaded_file = st.file_uploader(
        "Upload Document (PDF, DOCX, PPTX, CSV, TXT, MD)",
        type=["pdf", "docx", "pptx", "csv", "txt", "md"],
    )
    if uploaded_file and st.button("Ingest Uploaded File"):
        with st.spinner("Ingesting document..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                data = {"access_level": access_level}
                res = httpx.post(f"{api_base}/ingest", files=files, data=data, timeout=60.0)
                if res.status_code == 202:
                    job = res.json()
                    st.success(f"Ingestion queued! Job ID: {job.get('job_id')}")
                else:
                    st.error(f"Ingest failed: {res.text}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Error communicating with API: {e}")

    url_input = st.text_input("Scrape Web URL")
    if url_input and st.button("Ingest URL"):
        with st.spinner("Ingesting URL content..."):
            try:
                res = httpx.post(
                    f"{api_base}/ingest/url",
                    json={"url": url_input, "access_level": access_level},
                    timeout=30.0,
                )
                if res.status_code == 202:
                    st.success(f"URL queued! Job ID: {res.json().get('job_id')}")
                else:
                    st.error(f"URL ingest failed: {res.text}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Error: {e}")

    st.divider()

    col_ref, col_clr = st.columns(2)
    with col_ref:
        if st.button("🔄 Refresh"):
            st.rerun()
    with col_clr:
        if st.button("🧹 Clear Cache"):
            try:
                c_res = httpx.post(f"{api_base}/documents/cache/clear", timeout=5.0)
                if c_res.status_code == 200:
                    st.toast("Exact and semantic caches purged!")
                else:
                    st.error("Failed to clear cache")
            except Exception as e:
                st.error(f"Error: {e}")

    try:
        doc_res = httpx.get(f"{api_base}/documents", timeout=5.0)
        sum_res = httpx.get(f"{api_base}/documents/summaries", timeout=5.0)
        summaries_map = (
            {s["doc_id"]: s for s in sum_res.json().get("summaries", [])}
            if sum_res.status_code == 200
            else {}
        )

        if doc_res.status_code == 200:
            docs = doc_res.json().get("documents", [])
            if docs:
                for doc in docs:
                    with st.expander(f"📄 {doc['source_name']} ({doc['chunk_count']} chunks)"):
                        st.caption(f"ID: {doc['doc_id']} | Access: {doc['access_level']}")
                        s_info = summaries_map.get(doc['doc_id'])
                        if s_info:
                            st.markdown(f"**Topics:** {s_info.get('topics')}")
                            st.markdown(f"**Summary:** {s_info.get('summary')}")
                        elif doc.get("summary"):
                            st.caption(f"**Topics:** {doc['summary'][:160]}...")
                        if st.button("🗑️ Delete", key=f"del_{doc['doc_id']}"):
                            del_res = httpx.delete(f"{api_base}/documents/{doc['doc_id']}")
                            if del_res.status_code == 200:
                                st.toast(f"Deleted {doc['source_name']}")
                                st.rerun()
            else:
                st.info("No documents currently stored.")
    except Exception:  # noqa: BLE001
        st.caption("Backend unreachable or initializing.")

# Main Interface
st.markdown('<div class="main-header">🧠 AMCH-RAG Enterprise Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Agentic Multi-Modal Corrective Hybrid RAG with Guardrails, Caching, Memory & Model Gateway</div>',
    unsafe_allow_html=True,
)

# Render Chat History
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg.get("corrections"):
            for corr in msg["corrections"]:
                st.markdown(f'<div class="correction-badge">🔄 {corr}</div>', unsafe_allow_html=True)

        st.markdown(msg["content"])

        if msg.get("citations"):
            with st.expander(f"📚 Verified Sources ({len(msg['citations'])})"):
                for cit in msg["citations"]:
                    st.markdown(
                        f"""<div class="citation-box">
                        <b>[{cit.get('index')}] {cit.get('source')}</b> (Chunk: {cit.get('chunk_id')})
                        </div>""",
                        unsafe_allow_html=True,
                    )

        # Feedback actions for assistant responses
        if msg["role"] == "assistant" and msg.get("trace_id"):
            col1, col2, _ = st.columns([1, 1, 10])
            with col1:
                if st.button("👍", key=f"up_{idx}"):
                    httpx.post(f"{api_base}/feedback", json={"trace_id": msg["trace_id"], "rating": "up"})
                    st.toast("Feedback recorded: Helpful!")
            with col2:
                if st.button("👎", key=f"down_{idx}"):
                    httpx.post(f"{api_base}/feedback", json={"trace_id": msg["trace_id"], "rating": "down"})
                    st.toast("Feedback recorded: Unhelpful.")

# Query Input Handler
if prompt := st.chat_input("Ask a question about internal documents, tables, or charts..."):
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process Assistant Response via SSE Streaming
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        citations = []
        corrections = []
        trace_id = ""

        try:
            with httpx.stream(
                "POST",
                f"{api_base}/query",
                json={
                    "query": prompt,
                    "session_id": session_id,
                    "user_id": user_id,
                    "access_level": access_level,
                    "stream": True,
                },
                headers={"Accept": "text/event-stream"},
                timeout=60.0,
            ) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        event = json.loads(data_str)
                        event_type = event.get("type")

                        if event_type == "token":
                            full_response += event.get("content", "")
                            message_placeholder.markdown(full_response + "▌")
                        elif event_type == "citation":
                            citations.append(event)
                        elif event_type == "correction":
                            corrections.append(event.get("reason", "Correction triggered"))
                        elif event_type == "done":
                            trace_id = event.get("trace_id", "")
                        elif event_type == "error":
                            st.error(f"Error: {event.get('detail')}")

            message_placeholder.markdown(full_response)

            if citations:
                with st.expander(f"📚 Verified Sources ({len(citations)})"):
                    for cit in citations:
                        st.markdown(
                            f"""<div class="citation-box">
                            <b>[{cit.get('index')}] {cit.get('source')}</b> (Chunk: {cit.get('chunk_id')})
                            </div>""",
                            unsafe_allow_html=True,
                        )

            # Save in session state
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": full_response,
                    "citations": citations,
                    "corrections": corrections,
                    "trace_id": trace_id,
                }
            )

        except Exception as e:  # noqa: BLE001
            message_placeholder.markdown(f"⚠️ Failed to connect to backend: {e}")
