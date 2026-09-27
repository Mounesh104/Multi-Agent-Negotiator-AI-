"""
app.py — Streamlit UI for NegotiatorAI.

7 screens (per plan Section 8):
  1. Onboarding — business profile
  2. Deal Entry — item, price, terms, leverage
  3. Analyst Status — retrieval progress + evidence summary
  4. HITL Proposal Form — editable counter-offer + leverage points (REAL editable form)
  5. Rehearsal Chat — multi-turn with Vendor agent
  6. Scorecard — debrief + PDF export
  7. History Dashboard — past negotiations

RAG mode and LLM selector in sidebar.
"""

import os
import sys
import json
import uuid
import time
import html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# Fix #8: Centralise all project imports at the top instead of scattering
# inline imports across individual screen blocks. This avoids triple-import
# of load_history and makes dependency failures visible at startup.
from memory.sqlite_store import load_history as _load_history, get_summary_stats
from graph.pipeline import run_pipeline as _run_pipeline, run_post_rehearsal
from agents.vendor import run_vendor_turn
from export.pdf_export import generate_scorecard_pdf

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="NegotiatorAI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Styling — clean professional enterprise theme ─────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Main content ── */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1080px;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #1a1f2e !important;
    border-right: 1px solid #2d3347;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #c9d1e0 !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #f7fafc !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: 1px solid #2d3347 !important;
    color: #c9d1e0 !important;
    border-radius: 5px !important;
    font-size: 12px !important;
    font-weight: 400 !important;
    text-align: left !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #252b3d !important;
    color: #ffffff !important;
}
[data-testid="stSidebar"] hr {
    border-color: #2d3347 !important;
}
/* Sidebar select/dropdown stays dark */
[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: #252b3d !important;
    border-color: #2d3347 !important;
    color: #c9d1e0 !important;
}

/* ── Hero banner ── */
.hero-card {
    background: #1a1f2e;
    border-radius: 8px;
    padding: 1.5rem 2rem;
    color: #f7fafc;
    margin-bottom: 1.5rem;
    border-left: 4px solid #3b82f6;
}
.hero-card h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: #f7fafc;
    margin: 0 0 0.35rem;
}
.hero-card p {
    color: #a0aec0;
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.6;
}

/* ── White info panels ── */
.glass-panel {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    color: #2d3748;
    line-height: 1.75;
    font-size: 0.875rem;
}
.glass-panel p  { margin: 0.3rem 0; color: #2d3748; }
.glass-panel strong { color: #1a202c; font-weight: 600; }

/* ── Metric badge (analyst status screen) ── */
.metric-badge {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    text-align: center;
    font-weight: 600;
    color: #2d3748;
    font-size: 0.875rem;
}

/* ── Chat bubbles ── */
.chat-user {
    background: #1a1f2e;
    color: #f7fafc;
    border-radius: 8px 8px 2px 8px;
    padding: 0.65rem 1rem;
    margin: 0.5rem 0 0.5rem 25%;
    font-size: 0.875rem;
    line-height: 1.5;
}
.chat-vendor {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #2d3748;
    border-radius: 8px 8px 8px 2px;
    padding: 0.65rem 1rem;
    margin: 0.5rem 25% 0.5rem 0;
    font-size: 0.875rem;
    line-height: 1.5;
}

/* ── Metrics widgets ── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
}
[data-testid="stMetricLabel"] {
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
}

/* ── Dividers ── */
hr { border-color: #e2e8f0 !important; margin: 1rem 0 !important; }

/* ── Step dots ── */
.step-dot {
    width: 26px; height: 26px;
    border-radius: 50%;
    background: #e2e8f0;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 600; color: #718096;
}
.step-dot.active { background: #1a1f2e; color: white; }
.step-dot.done   { background: #38a169; color: white; }
</style>
""", unsafe_allow_html=True)


# ── Session State Init ─────────────────────────────────────────────────────
def init_state():
    defaults = {
        "screen": "onboarding",
        "business_id": "",
        "business_name": "",
        "industry": "",
        "deal_facts": {},
        "pipeline_state": {},
        "hitl_edited": {},
        "rehearsal_transcript": [],
        "scorecard": {},
        "history": [],
        "rag_mode": "agentic_rag",
        "llm_model": "openai/gpt-4o-mini",
        # Fix #9: removed unused "analyst_status" key (was set here but
        # never read or written anywhere else in the app)
        "session_id": str(uuid.uuid4())[:8],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# Fix #7 (updated for OpenRouter): Check for the primary API key at startup
# and surface a clear error instead of a cryptic auth exception in the pipeline.
from config import OPENROUTER_API_KEY as _OR_KEY, OPENAI_API_KEY as _OAI_KEY
_has_openrouter = bool(_OR_KEY) and not _OR_KEY.startswith("your_")
_has_openai     = bool(_OAI_KEY) and not _OAI_KEY.startswith("your_")

if not _has_openrouter and not _has_openai:
    st.error(
        "**No LLM API key configured.**  \n"
        "Open `.env` and add your **OPENROUTER_API_KEY** (recommended) "
        "or **OPENAI_API_KEY**, then restart the app.  \n"
        "Get an OpenRouter key at [openrouter.ai/keys](https://openrouter.ai/keys) — "
        "it gives access to GPT-4o, Claude, Llama, and more with one key."
    )
    st.stop()


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### NegotiatorAI")
    st.caption("Supplier negotiation intelligence platform")
    st.divider()

    st.markdown("**Pipeline Settings**")
    rag_mode = st.radio(
        "RAG Mode",
        options=["agentic_rag", "basic_rag", "no_rag"],
        format_func=lambda x: {"agentic_rag": "Agentic RAG", "basic_rag": "Basic RAG", "no_rag": "No RAG"}[x],
        index=["agentic_rag", "basic_rag", "no_rag"].index(st.session_state.rag_mode),
        help="Agentic RAG uses adaptive retrieval + reflection. Basic RAG uses single fixed query. No RAG uses LLM only.",
    )
    st.session_state.rag_mode = rag_mode

    llm_model = st.selectbox(
        "LLM Model",
        options=[
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-3-5-haiku",
            "anthropic/claude-3-5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-flash-1.5",
            "mistralai/mistral-7b-instruct",
        ],
        index=0 if st.session_state.llm_model not in [
            "openai/gpt-4o-mini", "openai/gpt-4o",
            "anthropic/claude-3-5-haiku", "anthropic/claude-3-5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-flash-1.5", "mistralai/mistral-7b-instruct",
        ] else [
            "openai/gpt-4o-mini", "openai/gpt-4o",
            "anthropic/claude-3-5-haiku", "anthropic/claude-3-5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "google/gemini-flash-1.5", "mistralai/mistral-7b-instruct",
        ].index(st.session_state.llm_model),
        help="All models route via OpenRouter. See openrouter.ai/models for the full list.",
    )
    st.session_state.llm_model = llm_model

    st.divider()

    # Navigation
    st.markdown("**Navigation**")
    screens = {
        "onboarding": "1  Business Profile",
        "deal_entry": "2  Deal Entry",
        "analyst_status": "3  Research",
        "hitl": "4  Strategy",
        "rehearsal": "5  Rehearsal",
        "scorecard": "6  Scorecard",
        "history": "7  History",
    }
    for screen_id, screen_label in screens.items():
        if st.button(screen_label, use_container_width=True, key=f"nav_{screen_id}"):
            st.session_state.screen = screen_id
            st.rerun()

    if st.session_state.business_id:
        st.divider()
        st.caption(st.session_state.business_name)
        st.caption(f"ID: {st.session_state.business_id}")
        st.caption(f"Mode: {rag_mode}")


# ── Screen Router ─────────────────────────────────────────────────────────
screen = st.session_state.screen


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 1: ONBOARDING
# ══════════════════════════════════════════════════════════════════════════
if screen == "onboarding":
    st.markdown("""
    <div class="hero-card">
        <h1>NegotiatorAI</h1>
        <p>
            AI-powered supplier negotiation intelligence.<br>
            Receive evidence-backed counter-offers, rehearse against a realistic supplier, and walk into every negotiation prepared.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Business Profile")
        business_name = st.text_input(
            "Business Name",
            value=st.session_state.business_name,
            placeholder="e.g. Spice Garden Restaurant",
            key="input_business_name"
        )
        industry = st.selectbox(
            "Industry",
            options=["Retail", "F&B / Restaurant", "Manufacturing", "Hospitality", "Construction", "Technology", "Healthcare", "Other"],
            index=0,
            key="input_industry"
        )
        business_id = st.text_input(
            "Business ID",
            value=st.session_state.business_id or business_name.lower().replace(" ", "_")[:20],
            placeholder="e.g. spice_garden_001",
            key="input_business_id",
            help="Used to store your negotiation history. Any unique string."
        )

    with col2:
        st.markdown("#### How it works")
        st.markdown("""
        <div class="glass-panel">
            <p><strong>Research</strong> &mdash; Retrieves negotiation tactics from a curated knowledge base</p>
            <p><strong>Strategy</strong> &mdash; Generates a grounded counter-offer with leverage points</p>
            <p><strong>Review</strong> &mdash; You edit and approve the strategy before proceeding</p>
            <p><strong>Rehearsal</strong> &mdash; Practice against an AI supplier until you are ready</p>
            <p><strong>Export</strong> &mdash; Download your negotiation brief as a PDF</p>
            <p><strong>Memory</strong> &mdash; Every deal is saved to build your negotiation history</p>
        </div>
        """, unsafe_allow_html=True)

        # Load history if business_id exists
        if st.session_state.business_id:
            hist = _load_history(st.session_state.business_id, limit=50)
            if hist:
                stats = get_summary_stats(st.session_state.business_id)
                st.markdown(f"""
                <div class="glass-panel">
                    <p><strong>Welcome back</strong></p>
                    <p>Past negotiations: <strong>{stats.get('total_deals', 0)}</strong></p>
                    <p>Estimated total savings: <strong>Rs.{stats.get('total_savings', 0):,.0f}</strong></p>
                </div>
                """, unsafe_allow_html=True)

    st.divider()
    if st.button("Continue to Deal Entry", type="primary", use_container_width=True):
        if not business_name.strip():
            st.error("Please enter your business name.")
        else:
            st.session_state.business_name = business_name.strip()
            st.session_state.business_id = business_id.strip() or business_name.lower().replace(" ", "_")[:20]
            st.session_state.industry = industry
            st.session_state.screen = "deal_entry"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 2: DEAL ENTRY
# ══════════════════════════════════════════════════════════════════════════
elif screen == "deal_entry":
    st.markdown("## Enter Deal Details")
    st.caption("Enter the supplier quote you want to negotiate.")

    with st.form("deal_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Pricing & Item")
            item = st.text_input("What are you buying?", placeholder="e.g. Corrugated cardboard boxes")
            category = st.selectbox("Category", ["packaging", "raw_materials", "equipment", "service", "logistics", "office_supplies"])
            quantity = st.text_input("Quantity / Order Size", placeholder="e.g. 500 units per month")
            quoted_price = st.number_input("Supplier's Quoted Price", min_value=0.0, step=0.01, format="%.2f")
            price_unit = st.selectbox("Price Unit", ["per unit", "per kg", "per month", "total", "per shipment", "per set"])
            supplier_name = st.text_input("Supplier Name (optional)", placeholder="e.g. ABC Packaging Co.")

        with col2:
            st.markdown("#### Terms & Leverage")
            payment_terms = st.selectbox("Supplier's Payment Terms", ["Net 15", "Net 30", "Net 45", "Net 60", "Advance", "50% Advance + 50% on delivery"])
            delivery_days = st.number_input("Quoted Lead Time (days)", min_value=0, value=7)

            st.markdown("---")
            st.markdown("**Leverage factors** (check all that apply)")
            is_repeat = st.checkbox("I am a repeat customer")
            repeat_count = 0
            cumulative_spend = 0.0
            if is_repeat:
                repeat_count = st.number_input("Number of past orders", min_value=1, value=1, key="rc")
                cumulative_spend = st.number_input("Total past spend (₹)", min_value=0.0, value=0.0, key="cs")

            has_competing = st.checkbox("I have competing quotes")
            competing_price = 0.0
            competing_count = 0
            if has_competing:
                competing_count = st.number_input("Number of competing quotes", min_value=1, value=2, key="cc")
                competing_price = st.number_input("Best competing price", min_value=0.0, value=0.0, key="cp")

            can_commit = st.checkbox("I can offer a volume commitment")
            commit_months = 0
            if can_commit:
                commit_months = st.number_input("Commitment duration (months)", min_value=1, max_value=24, value=6, key="cm")

            urgency = st.select_slider("Your urgency level", options=["low", "medium", "high"], value="medium")

        additional_context = st.text_area(
            "Additional context (optional)",
            placeholder="Anything else relevant: past quality issues, special requirements, market conditions...",
            height=80,
        )

        submitted = st.form_submit_button("Analyze Deal", type="primary", use_container_width=True)

    if submitted:
        if not item.strip():
            st.error("Please enter what you are buying.")
        elif quoted_price <= 0:
            st.error("Please enter a valid quoted price.")
        else:
            st.session_state.deal_facts = {
                "item": item.strip(),
                "category": category,
                "quantity": quantity,
                "quoted_price": quoted_price,
                "quoted_price_unit": price_unit,
                "payment_terms": payment_terms,
                "delivery_days": int(delivery_days),
                "supplier_name": supplier_name.strip(),
                "industry": st.session_state.industry,
                "is_repeat_customer": is_repeat,
                "repeat_order_count": int(repeat_count),
                "cumulative_spend": float(cumulative_spend),
                "has_competing_quotes": has_competing,
                "competing_quote_price": float(competing_price),
                "competing_quote_count": int(competing_count),
                "can_commit_volume": can_commit,
                "commitment_months": int(commit_months),
                "urgency": urgency,
                "additional_context": additional_context.strip(),
            }
            st.session_state.pipeline_state = {}  # reset
            st.session_state.screen = "analyst_status"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 3: ANALYST STATUS (runs pipeline)
# ══════════════════════════════════════════════════════════════════════════
elif screen == "analyst_status":
    st.markdown("## Researching Negotiation Tactics")

    deal = st.session_state.deal_facts
    if not deal:
        st.warning("No deal entered. Please go back to Deal Entry.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div class="metric-badge">📦 {html.escape(str(deal.get('item', 'N/A')))}</div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-badge">💰 {html.escape(str(deal.get('quoted_price', 0)))} {html.escape(str(deal.get('quoted_price_unit', '')))}</div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-badge">🏷️ {html.escape(deal.get('category', 'N/A').replace('_', ' ').title())}</div>""", unsafe_allow_html=True)

    st.divider()

    # Run pipeline if not already done
    if not st.session_state.pipeline_state.get("analyst_summary"):
        with st.status("Running pipeline...", expanded=True) as status:
            st.write("📂 Loading your negotiation history...")
            history = _load_history(st.session_state.business_id)

            rag_label = {"agentic_rag": "Agentic RAG (adaptive retrieval)", "basic_rag": "Basic RAG (single query)", "no_rag": "No RAG (LLM only)"}
            st.write(f"🔬 Mode: **{rag_label.get(st.session_state.rag_mode, st.session_state.rag_mode)}**")
            st.write("🔍 Querying negotiation knowledge base...")

            initial_state = {
                "business_id": st.session_state.business_id,
                "business_name": st.session_state.business_name,
                "deal_facts": deal,
                "rag_mode": st.session_state.rag_mode,
                "llm_model": st.session_state.llm_model,
                "history": history,
                "session_id": st.session_state.session_id,
            }

            try:
                pipeline_state = _run_pipeline(initial_state)
                st.session_state.pipeline_state = pipeline_state
                status.update(label="✅ Research complete!", state="complete")
            except Exception as e:
                status.update(label=f"❌ Error: {e}", state="error")
                st.error(f"Pipeline error: {e}")
                st.exception(e)
                st.stop()

    state = st.session_state.pipeline_state
    analyst_summary_raw = state.get("analyst_summary", "{}")
    queries = state.get("retrieval_queries", [])
    web_used = state.get("web_search_used", False)
    reflection_passed = state.get("reflection_passed", True)
    requery_iter = state.get("requery_iteration", 0)

    # Parse analyst summary
    try:
        if isinstance(analyst_summary_raw, str):
            analyst_data = json.loads(analyst_summary_raw)
        else:
            analyst_data = analyst_summary_raw or {}
    except Exception:
        analyst_data = {"analyst_summary": analyst_summary_raw}

    # Display research status
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Retrieval Queries", len(queries))
    with col2:
        ev_count = len(state.get("retrieved_evidence", []))
        st.metric("Evidence Chunks", ev_count)
    with col3:
        strength = analyst_data.get("evidence_strength", "N/A")
        color_map = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
        st.metric("Evidence Strength", f"{color_map.get(strength, '⚪')} {strength.title()}")
    with col4:
        if web_used:
            st.metric("Web Search", "✅ Used")
        else:
            st.metric("Web Search", "Not needed")

    if requery_iter > 0:
        st.info(f"♻️ Re-retrieval triggered {requery_iter}x — Strategist wasn't satisfied with initial evidence")

    # Queries used (expandable)
    if queries:
        with st.expander("🔎 Retrieval Queries Used"):
            for i, q in enumerate(queries, 1):
                st.markdown(f"**Query {i}:** `{q}`")

    # Evidence summary
    st.markdown("#### 📋 Evidence Summary")
    summary_text = analyst_data.get("analyst_summary", "No summary available.")
    st.markdown(f"""<div class="glass-panel">{summary_text}</div>""", unsafe_allow_html=True)

    # Applicable tactics
    tactics = analyst_data.get("applicable_tactics", [])
    if tactics:
        with st.expander("🎯 Applicable Tactics Found"):
            for t in tactics:
                st.markdown(f"• {t}")

    # Benchmarks
    benchmarks = analyst_data.get("relevant_benchmarks", [])
    if benchmarks:
        with st.expander("📊 Relevant Benchmarks"):
            for b in benchmarks:
                st.markdown(f"• {b}")

    # Retrieved evidence chunks
    evidence = state.get("retrieved_evidence", [])
    if evidence:
        with st.expander(f"📄 Raw Evidence ({len(evidence)} chunks)"):
            for i, doc in enumerate(evidence[:5], 1):
                src = os.path.basename(doc.metadata.get("source", "unknown")) if hasattr(doc, "metadata") else "unknown"
                content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                st.markdown(f"**[{i}] {src}**")
                st.text(content[:300] + "..." if len(content) > 300 else content)
                st.divider()

    st.divider()
    if st.button("View Your Strategy →", type="primary", use_container_width=True):
        st.session_state.screen = "hitl"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 4: HITL PROPOSAL (editable form — REAL edit, not a button)
# ══════════════════════════════════════════════════════════════════════════
elif screen == "hitl":
    st.markdown("## Review & Edit Strategy")
    st.info("Human-in-the-loop checkpoint. The AI has drafted a strategy — review and edit any field before proceeding to rehearsal.")

    state = st.session_state.pipeline_state
    if not state:
        st.warning("No strategy generated yet. Please complete Deal Entry and Research first.")
        st.stop()

    draft = state.get("strategist_draft", {})
    deal = st.session_state.deal_facts
    quoted = deal.get("quoted_price", 0)

    # Pre-fill from draft or existing edit
    existing = st.session_state.hitl_edited or draft

    st.markdown("#### 📊 AI-Generated Draft (editable below)")
    col1, col2 = st.columns([1, 1])
    with col1:
        orig_pct = existing.get("counter_offer_pct", 88.0)
        st.markdown(f"*AI suggested: **{orig_pct:.1f}%** of quoted price ({100-orig_pct:.1f}% discount)*")

    st.divider()

    with st.form("hitl_form"):
        st.markdown("#### 💰 Counter-Offer")
        col1, col2 = st.columns(2)
        with col1:
            counter_pct = st.number_input(
                "Counter-offer as % of quoted price",
                min_value=50.0, max_value=100.0,
                value=float(existing.get("counter_offer_pct", 88.0)),
                step=0.5,
                format="%.1f",
                help="e.g. 85 means you're asking for a 15% discount from the quoted price",
                key="hitl_counter_pct"
            )
        with col2:
            counter_amount = quoted * (counter_pct / 100) if quoted else 0
            st.metric("Counter-offer Amount", f"₹{counter_amount:,.2f}", delta=f"-₹{quoted - counter_amount:,.2f}")

        st.markdown("#### 🎯 Primary Tactic")
        primary_tactic = st.text_area(
            "Your main negotiation approach",
            value=existing.get("primary_tactic", ""),
            height=80,
            key="hitl_primary",
            help="Edit the AI's suggested approach or write your own"
        )

        st.markdown("#### 🔄 Alternative Asks (non-price)")
        st.caption("If the supplier won't move on price, what else will you ask for?")
        default_alts = existing.get("alt_asks", ["", "", ""])
        while len(default_alts) < 3:
            default_alts.append("")
        alt1 = st.text_input("Alternative Ask 1", value=default_alts[0] if len(default_alts) > 0 else "", key="alt1", placeholder="e.g. Net 60 payment terms")
        alt2 = st.text_input("Alternative Ask 2", value=default_alts[1] if len(default_alts) > 1 else "", key="alt2", placeholder="e.g. Free delivery for all orders")
        alt3 = st.text_input("Alternative Ask 3", value=default_alts[2] if len(default_alts) > 2 else "", key="alt3", placeholder="e.g. 2% early payment discount")

        st.markdown("#### 💪 Leverage Points")
        st.caption("Your reasons for the discount — be specific. The Vendor agent will respond to these.")
        default_lp = existing.get("leverage_points", ["", "", ""])
        while len(default_lp) < 3:
            default_lp.append("")
        lp1 = st.text_area("Leverage Point 1", value=default_lp[0] if len(default_lp) > 0 else "", height=60, key="lp1", placeholder="e.g. We are a repeat customer with 14 orders totaling ₹65,000")
        lp2 = st.text_area("Leverage Point 2", value=default_lp[1] if len(default_lp) > 1 else "", height=60, key="lp2", placeholder="e.g. We have 2 competing quotes at 10% below your price")
        lp3 = st.text_area("Leverage Point 3", value=default_lp[2] if len(default_lp) > 2 else "", height=60, key="lp3", placeholder="e.g. We are prepared to commit to a 12-month agreement")

        st.markdown("#### 🗣️ Opening Script")
        opening = st.text_area(
            "Your opening statement (use verbatim or adapt)",
            value=existing.get("opening_script", ""),
            height=100,
            key="hitl_opening",
        )

        submitted = st.form_submit_button("Confirm Strategy & Start Rehearsal", type="primary", use_container_width=True)

    if submitted:
        leverage_points = [lp for lp in [lp1, lp2, lp3] if lp.strip()]
        alt_asks = [a for a in [alt1, alt2, alt3] if a.strip()]

        # Store user-edited values — these are what carry into the rehearsal
        st.session_state.hitl_edited = {
            "counter_offer_pct": counter_pct,
            "counter_offer_amount": quoted * (counter_pct / 100),
            "primary_tactic": primary_tactic,
            "alt_asks": alt_asks,
            "leverage_points": leverage_points,
            "opening_script": opening,
        }
        # Also update pipeline state so PDF export uses edited version
        st.session_state.pipeline_state["hitl_edited"] = st.session_state.hitl_edited

        st.success("Strategy saved. Starting rehearsal.")
        st.session_state.screen = "rehearsal"
        st.session_state.rehearsal_transcript = []
        st.rerun()

    # Show AI reasoning (collapsible)
    if draft.get("reasoning"):
        with st.expander("🤖 AI Reasoning (why these recommendations?)"):
            st.markdown(draft.get("reasoning", ""))
            if draft.get("confidence"):
                conf = draft["confidence"]
                badge = {"high": "🟢 High", "medium": "🟡 Medium", "low": "🔴 Low"}.get(conf, conf)
                st.markdown(f"**Confidence:** {badge}")
            ungrounded = draft.get("ungrounded_items", [])
            if ungrounded:
                st.warning(f"⚠️ Ungrounded items: {', '.join(ungrounded)}")


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 5: REHEARSAL CHAT
# ══════════════════════════════════════════════════════════════════════════
elif screen == "rehearsal":
    st.markdown("## Negotiation Rehearsal")
    st.caption("Practice your negotiation against an AI supplier. The vendor will resist — use your leverage points.")

    hitl = st.session_state.hitl_edited
    deal = st.session_state.deal_facts

    if not hitl:
        st.warning("Please complete the strategy step first.")
        st.stop()

    # Show proposal summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Your Target", f"{hitl.get('counter_offer_pct', 0):.1f}% of quote")
    with col2:
        st.metric("Counter Amount", f"₹{hitl.get('counter_offer_amount', 0):,.2f}")
    with col3:
        st.metric("Leverage Points", len(hitl.get("leverage_points", [])))

    # Show opening script
    if hitl.get("opening_script"):
        with st.expander("💬 Your Opening Script (click to expand)", expanded=False):
            st.info(hitl["opening_script"])

    st.divider()

    # Display chat history
    transcript = st.session_state.rehearsal_transcript
    for turn in transcript:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            st.markdown(f'<div class="chat-user"><strong>You</strong><br>{html.escape(content)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-vendor"><strong>Supplier</strong><br>{html.escape(content)}</div>', unsafe_allow_html=True)

    if not transcript:
        st.markdown("""
        <div class="glass-panel" style="text-align:center; padding: 2rem;">
            <p style="font-size: 1.2rem;">🎯 Ready to practice?</p>
            <p>Type your opening statement below and the AI supplier will respond.<br>
            Use your leverage points and try to get to your target price!</p>
        </div>
        """, unsafe_allow_html=True)

    # Chat input
    if not st.session_state.get("rehearsal_done", False):
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                user_input = st.text_input(
                    "Your message",
                    placeholder="Type your negotiation message here...",
                    label_visibility="collapsed",
                    key="chat_input"
                )
            with col2:
                send = st.form_submit_button("Send →", type="primary", use_container_width=True)

        if send and user_input.strip():
            transcript.append({"role": "user", "content": user_input.strip()})

            with st.spinner("Supplier is responding..."):
                vendor_response = run_vendor_turn(
                    user_message=user_input.strip(),
                    transcript=transcript[:-1],  # history without latest user message
                    deal_facts=deal,
                    hitl_proposal=hitl,
                    llm_model=st.session_state.llm_model,
                )
            transcript.append({"role": "vendor", "content": vendor_response})
            st.session_state.rehearsal_transcript = transcript
            st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            if transcript and st.button("End Rehearsal & Get Scored", type="primary", use_container_width=True):
                st.session_state.rehearsal_done = True
                st.session_state.screen = "scorecard"
                # Update pipeline state with transcript
                st.session_state.pipeline_state["rehearsal_transcript"] = transcript
                st.session_state.pipeline_state["hitl_edited"] = hitl
                st.rerun()
        with col2:
            if st.button("Restart Rehearsal", use_container_width=True):
                st.session_state.rehearsal_transcript = []
                st.session_state.rehearsal_done = False
                st.rerun()
    else:
        st.success("Rehearsal complete! View your scorecard.")
        if st.button("View Scorecard →", type="primary"):
            st.session_state.screen = "scorecard"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 6: SCORECARD
# ══════════════════════════════════════════════════════════════════════════
elif screen == "scorecard":
    st.markdown("## Scorecard")

    # Generate scorecard if not done
    if not st.session_state.scorecard:
        with st.spinner("Generating scorecard and coaching..."):
            state = st.session_state.pipeline_state
            state["rehearsal_transcript"] = st.session_state.rehearsal_transcript
            state["deal_facts"] = st.session_state.deal_facts
            state["hitl_edited"] = st.session_state.hitl_edited
            state["llm_model"] = st.session_state.llm_model

            try:
                final_state = run_post_rehearsal(state)
                st.session_state.pipeline_state.update(final_state)
                st.session_state.scorecard = final_state.get("scorecard", {})
            except Exception as e:
                st.error(f"Scoring error: {e}")
                st.session_state.scorecard = {"overall_score": 0, "coaching_notes": str(e)}

    scorecard = st.session_state.scorecard

    if scorecard.get("overall_score", 0) > 0:
        # Score display
        col1, col2, col3, col4, col5 = st.columns(5)
        def score_color(s):
            if s >= 4: return "#38a169"   # green
            elif s >= 3: return "#d69e2e"  # amber
            return "#e53e3e"              # red

        scores = [
            ("Overall", scorecard.get("overall_score", 0)),
            ("Assertiveness", scorecard.get("assertiveness", 0)),
            ("Leverage Use", scorecard.get("leverage_use", 0)),
            ("Pushback Handling", scorecard.get("pushback_handling", 0)),
            ("Closing Technique", scorecard.get("closing_technique", 0)),
        ]
        for col, (label, score) in zip([col1, col2, col3, col4, col5], scores):
            with col:
                color = score_color(score)
                st.markdown(f"""
                <div style="text-align:center; background:#ffffff; border-radius:8px; padding:0.9rem 0.5rem; border: 1px solid #e2e8f0; border-top: 3px solid {color};">
                    <div style="font-size:1.75rem; font-weight:700; color:{color};">{score:.1f}</div>
                    <div style="font-size:0.72rem; color:#718096; margin-top:0.2rem; font-weight:500; text-transform:uppercase; letter-spacing:0.04em;">{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Coach Notes")
            st.info(scorecard.get("coaching_notes", ""))

            strengths = scorecard.get("strengths", [])
            if strengths:
                st.markdown("**Strengths**")
                for s in strengths:
                    st.markdown(f"- {s}")

        with col2:
            improvements = scorecard.get("improvements", [])
            if improvements:
                st.markdown("**Areas to improve**")
                for imp in improvements:
                    st.markdown(f"- {imp}")

            est_outcome = scorecard.get("estimated_outcome", "")
            if est_outcome:
                st.markdown("**Estimated real-world outcome**")
                st.markdown(f"> {est_outcome}")

        # Improved script
        final_script = scorecard.get("final_script", "")
        if final_script:
            st.divider()
            st.markdown("#### Improved Opening Script")
            st.success(f'"{final_script}"')

    else:
        st.info("Complete a rehearsal to see your score here.")

    st.divider()

    # PDF Export
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generate & Download PDF", type="primary", use_container_width=True):
            state = st.session_state.pipeline_state
            state["business_name"] = st.session_state.business_name
            state["deal_facts"] = st.session_state.deal_facts
            state["scorecard"] = st.session_state.scorecard
            state["hitl_edited"] = st.session_state.hitl_edited
            state["rag_mode"] = st.session_state.rag_mode

            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_scorecard_pdf(state)

            deal = st.session_state.deal_facts
            fname = f"negotiation_{deal.get('item', 'deal').replace(' ', '_')[:20]}.pdf"
            st.download_button(
                label="⬇️ Download Cheat Sheet PDF",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )

    with col2:
        if st.button("Start New Negotiation", use_container_width=True):
            # Reset all deal-level state for a fresh negotiation
            for key in ["deal_facts", "pipeline_state", "hitl_edited", "rehearsal_transcript", "scorecard", "rehearsal_done"]:
                st.session_state[key] = {} if key in ["deal_facts", "pipeline_state", "hitl_edited", "scorecard"] else [] if key == "rehearsal_transcript" else False
            # Fix #4: generate a fresh session_id so each negotiation has its
            # own unique identifier in SQLite — the old id was being reused.
            st.session_state.session_id = str(uuid.uuid4())[:8]
            st.session_state.screen = "deal_entry"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SCREEN 7: HISTORY DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
elif screen == "history":
    st.markdown("## Negotiation History")

    if not st.session_state.business_id:
        st.warning("Please complete onboarding first.")
        st.stop()

    history = _load_history(st.session_state.business_id, limit=50)
    stats = get_summary_stats(st.session_state.business_id)

    if not history:
        st.info("No past negotiations yet. Complete your first deal to see history here.")
        st.stop()

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Deals", stats.get("total_deals", 0))
    with col2:
        total_savings = stats.get("total_savings") or 0
        st.metric("Est. Total Savings", f"₹{total_savings:,.0f}")
    with col3:
        avg_score = stats.get("avg_score") or 0
        st.metric("Avg Rehearsal Score", f"{avg_score:.1f}/5")
    with col4:
        avg_discount = stats.get("avg_discount_pct") or 0
        st.metric("Avg Counter-Offer", f"{avg_discount:.1f}% of quote")

    st.divider()

    # History table
    import pandas as pd
    df_rows = []
    for h in history:
        df_rows.append({
            "Date": h.get("timestamp", "")[:10],
            "Item": h.get("item", ""),
            "Category": h.get("category", ""),
            "Supplier": h.get("supplier_name", ""),
            "Quoted": f"₹{h.get('quoted_price', 0):,.0f}",
            "Counter-Offer %": f"{h.get('counter_offer_pct', 0):.1f}%",
            "Est. Savings": f"₹{h.get('estimated_savings', 0):,.0f}",
            "Score": f"{h.get('overall_score', 0):.1f}/5",
            "Mode": h.get("rag_mode", ""),
            "Outcome": h.get("final_outcome", "Pending"),
        })

    df = pd.DataFrame(df_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Per-category analysis
    if len(history) >= 3:
        st.markdown("#### 📊 Savings by Category")
        cat_data = {}
        for h in history:
            cat = h.get("category", "other")
            cat_data[cat] = cat_data.get(cat, 0) + (h.get("estimated_savings") or 0)

        if cat_data:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.barh(list(cat_data.keys()), list(cat_data.values()), color="#1a1f2e", height=0.5)
            ax.set_xlabel("Estimated Savings (Rs.)", fontsize=11, color="#4a5568")
            ax.set_title("Savings by Category", fontsize=12, fontweight="600", color="#1a202c", pad=12)
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#ffffff")
            ax.tick_params(colors="#4a5568", labelsize=10)
            ax.title.set_color("#1a202c")
            ax.xaxis.label.set_color("#4a5568")
            for spine in ax.spines.values():
                spine.set_edgecolor("#e2e8f0")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.grid(axis="x", color="#e2e8f0", linewidth=0.8)
            ax.set_axisbelow(True)
            st.pyplot(fig)
            plt.close(fig)  # Security/memory fix: release figure after render
