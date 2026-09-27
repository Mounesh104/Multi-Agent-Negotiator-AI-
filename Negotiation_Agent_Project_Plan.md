# NegotiatorAI — Vendor & Supplier Negotiation Agent for Small Businesses
### Mini Project Plan (Agentic AI System)

---

## 1. Problem Definition

**Real-world problem:**
Small businesses (retail shops, restaurants, manufacturers, salons, service providers) regularly negotiate purchase deals with suppliers/vendors — raw materials, inventory, packaging, ingredients, equipment rental, AMC/service contracts. Most small business owners:
- Don't know standard negotiation levers (bulk discounts, payment terms, delivery penalties, loyalty leverage).
- Accept the first quote because they lack time/expertise to push back effectively.
- Have no memory of past negotiations to use as leverage ("last time we settled at X%").

**Motivation:**
This is a *universal, recurring* pain across small business types — unlike salary negotiation (once a year) or project costing (only relevant to freelancers/agencies). Every small business negotiates purchases regularly, and the negotiation *mechanics* (not the item-specific pricing) generalize across industries.

**Users:** Small business owners/procurement staff — retail, F&B, manufacturing, services.

**Expected outcomes:**
1. A data-backed counter-offer and negotiation strategy for a specific vendor quote.
2. A rehearsed negotiation script the user has practiced against a simulated vendor.
3. An exportable "negotiation cheat sheet" to use in the real conversation.
4. A growing history of past negotiations per business, used as leverage/anchoring in future deals.

---

## 2. Agent Architecture Design

### Why multi-agent (justification)
Three genuinely distinct objectives/personas are required, and mixing them in a single prompt causes role confusion:
- **Analyst** — objective, evidence-gathering, no opinion.
- **Strategist** — user-aligned, persuasive, must reflect on gaps in leverage.
- **Vendor (adversary)** — must argue *against* the user's interest to create a realistic rehearsal; a single agent cannot simultaneously advocate for and against the user reliably.

Separating them also lets each be evaluated independently (Section 6) and keeps prompts short and role-focused.

### Architecture diagram (conceptual)

```
User Input (quote details, item, price, terms, leverage)
        │
        ▼
   [ Analyst Agent ] ── retrieval tool ──> Negotiation Knowledge Base (Chroma)
        │                                   + web_search (category pricing, optional)
        ▼
   [ Strategist Agent ] ──reflect──> (confidence low? → ask Analyst to re-retrieve)
        │
        ▼
   HUMAN-IN-THE-LOOP CHECKPOINT (review/edit counter-offer & leverage points)
        │
        ▼
   [ Vendor Agent ] <──rehearsal loop (multi-turn)──> User
        │
        ▼
   Strategist scores the rehearsal, generates final Scorecard / Cheat Sheet (export)
        │
        ▼
   Persistent Memory Store (past negotiations, savings, patterns per business)
```

### Prompts, tools, memory, reasoning loop summary

| Component | Detail |
|---|---|
| **Prompts** | Role-specific system prompts per agent (Analyst = neutral researcher; Strategist = user's advocate/coach; Vendor = realistic, mildly resistant counterparty) |
| **Tools** | `retrieve_tactics(query)` — vector search over knowledge base; `web_search(query)` — optional live category pricing; `save_negotiation(record)` / `load_history(business_id)` — memory read/write |
| **Memory** | Short-term: LangGraph state (current deal details, conversation turns). Long-term: SQLite/JSON store keyed by business_id, holding past deals, outcomes, and savings |
| **Reasoning loop** | Analyst retrieves → Strategist drafts → self-reflection check ("is this grounded in retrieved evidence + user's stated leverage?") → re-retrieve if weak → HITL approval → rehearsal loop → scorecard |

---

## 3. Core Agent Capabilities

**a. Reflection / self-correction**
Strategist evaluates its own draft counter-offer against two things: (1) retrieved tactic/benchmark evidence, (2) the leverage info the user actually provided. If the offer isn't grounded (e.g., no evidence found, or user gave no leverage info), it does NOT guess — it either re-triggers Analyst retrieval with a narrower query, or asks the user a clarifying question.

**b. Tool usage / retrieval**
- `retrieve_tactics` — semantic search over curated negotiation knowledge base.
- `web_search` — optional, for category-specific pricing context.
- Memory read/write tools for persistence.

**c. Stateful behavior and memory**
- In-session: full negotiation state (deal facts, retrieved evidence, rehearsal transcript) held in LangGraph state object, passed between nodes.
- Cross-session: business profile with negotiation history, retrievable at the start of a new session and usable as an anchor ("last time with this supplier, you settled 8% below asking").

---

## 4. Agentic RAG (Mandatory)

**Knowledge base (build in Day 1–2):** 20–30 curated documents/snippets covering:
- Bulk/volume discount norms
- Payment term negotiation (30/60/90-day terms, early-payment discounts)
- Delivery & quality penalty clauses
- Loyalty/repeat-customer leverage tactics
- Multi-vendor / competing-quote leverage tactics
- General negotiation psychology (anchoring, BATNA, silence tactics)

Sources: public small-business procurement guides, negotiation-tactics articles, SME advisory content (compile into markdown/text files → chunk → embed).

**Agent-driven retrieval strategy (what makes it "agentic," not basic RAG):**
The Analyst does **not** run one fixed query. It decides what to retrieve based on the specifics of the deal:
1. First retrieval: general tactics for the item category (e.g., "packaging materials bulk discount").
2. If the user mentioned they're a repeat customer → triggers a second, targeted retrieval on loyalty leverage.
3. If Strategist's confidence check fails (no strong grounding) → Analyst re-queries with a narrower or rephrased query.
4. If item is unusual/no good KB match → falls back to `web_search`.

This adaptive, multi-step, condition-triggered retrieval is the core "agentic RAG" behavior to highlight in the report.

**Baseline comparison (build all three, mandatory):**
| Condition | Behavior |
|---|---|
| **No-RAG** | Strategist generates counter-offer/tactics purely from LLM parametric knowledge, no retrieval at all |
| **Basic RAG** | Single fixed retrieval query per deal, straight into the answer, no reflection or re-querying |
| **Agentic RAG** | Full loop above: adaptive queries, reflection-triggered re-retrieval, fallback to web search |

Run the same 8–10 test deals through all three conditions for the Evaluation section (Section 6).

---

## 5. Collaboration / HITL (at least one — this project has both)

**Multi-agent interaction:** Analyst → Strategist → Vendor, as above — a genuine 3-role pipeline plus a rehearsal loop between Strategist (via scoring) and Vendor.

**Human-in-the-loop validation (structurally necessary, not decorative):**
The agent cannot know the user's true relationship with the supplier, urgency, or budget ceiling — so the user MUST review and can edit the Strategist's proposed counter-offer and leverage points before the rehearsal proceeds. This is a real approval gate, not a rubber-stamp — build it as an actual editable form/step in the UI, not just a "continue?" button.

---

## 6. Evaluation

**Test set:** 8–10 sample vendor deals varying by:
- Item type (raw material, packaging, service contract, equipment)
- Deal size (small vs. large order)
- User leverage (first-time buyer vs. repeat customer vs. multiple competing quotes)

**Metrics:**
| Metric | How measured |
|---|---|
| **Accuracy** | Does the retrieved tactic/benchmark actually match the deal's category and leverage type? (manual rubric-check against the KB) |
| **Reasoning quality** | Does the Strategist's justification cite specific retrieved evidence + user-provided leverage, vs. generic/vague advice? (1–5 manual score) |
| **Response consistency** | Run the same deal 3× — measure variance in the recommended counter-offer % and tactics suggested |
| **RAG condition comparison** | Score No-RAG vs. Basic RAG vs. Agentic RAG on the above three metrics — present as a comparison table |
| **LLM comparison** | Run the full pipeline with 2–3 LLMs (e.g., GPT-4o-mini, Claude Haiku/Sonnet, Llama-3 via Groq) — compare cost, latency, reasoning quality, consistency |
| **Rehearsal effectiveness** | Compare user's first rehearsal attempt vs. second attempt after Strategist coaching — qualitative before/after |

Present results as tables/charts in the report — this is the section graders weight heavily, so don't skip the baseline and LLM comparisons even under time pressure.

---

## 7. Tech Stack

- **Orchestration:** LangGraph (explicit state, conditional edges for reflection/re-retrieval loops)
- **Vector store:** Chroma (local, no setup overhead)
- **Embeddings + LLMs:** OpenAI (GPT-4o-mini) as primary; add Claude and/or Llama-3 (Groq) for the LLM comparison in evaluation
- **Web search tool:** Tavily or SerpAPI (for optional category pricing lookups)
- **Persistent memory:** SQLite (simple schema: business_id, deal records, timestamps, outcomes)
- **UI / product layer:** Streamlit (fast to build, still presentable as a real product)
- **Deployment:** Streamlit Community Cloud (free, gives a real public URL for the demo)
- **Export:** Cheat-sheet/scorecard exported as PDF (use a lightweight lib like `fpdf` or `reportlab`)

---

## 8. Product Flow (End-to-End)

1. **Onboarding** — business profile (name, industry, business_id).
2. **Deal entry** — item, quantity, supplier's quoted price, payment terms, user's leverage info (repeat customer? competing quotes? urgency?).
3. **Analyst retrieval** — shown to user as "Researching negotiation tactics..." with a summary of what was retrieved.
4. **Strategist proposal (HITL)** — counter-offer, 2–3 alternative asks, leverage points — editable by user before proceeding.
5. **Rehearsal** — multi-turn chat with Vendor agent; user practices delivering the pitch and handling pushback.
6. **Scorecard** — debrief: what worked, what to improve, final recommended script — exportable as PDF.
7. **History dashboard** — past negotiations, tactics used, estimated savings, patterns per supplier.

---

## 9. Day-by-Day Build Plan (flexible hours, ~1 week)

| Day | Tasks |
|---|---|
| **Day 1** | Finalize scope; write negotiation knowledge base (20–30 curated docs); set up Chroma + embeddings; test basic retrieval |
| **Day 2** | Build Analyst agent (adaptive retrieval logic) + Strategist agent (draft counter-offer + reflection/re-query condition) in LangGraph |
| **Day 3** | Build No-RAG and Basic-RAG baseline variants (strip features from the agentic version); wire up SQLite memory (save/load business history) |
| **Day 4** | Build Vendor (adversary) agent + multi-turn rehearsal loop; add Strategist scoring/coaching after rehearsal |
| **Day 5** | Build Streamlit UI: onboarding → deal entry → HITL review/edit step → rehearsal chat → scorecard export → history dashboard |
| **Day 6** | Run evaluation: 8–10 test deals × 3 RAG conditions × 2–3 LLMs; log results into comparison tables/charts |
| **Day 7** | Deploy to Streamlit Cloud; write report (problem, architecture, capabilities, RAG comparison, HITL justification, evaluation results); record demo video |

---

## 10. Report Structure (for submission)

1. Problem Definition & Motivation
2. Agent Architecture (diagram + component table from Section 2)
3. Core Capabilities (reflection, tools, memory — with code/screenshot evidence)
4. Agentic RAG Design + Baseline Comparison (Section 4/6 results)
5. Multi-Agent & HITL Design (Section 5, with screenshot of the approval step)
6. Evaluation Results (tables/charts from Section 6)
7. Limitations & Future Work (e.g., generalization across item categories, accuracy depends on user-supplied inputs, possible expansion to other negotiation types)
8. Demo link + screenshots

---

## Known Limitation to State Explicitly in the Report
The agent's recommendations are only as good as the user-supplied deal facts (price, leverage) — it does not independently verify market prices for every possible item category, since that data doesn't generalize across industries. This is a deliberate scope decision (trading deep price-accuracy for cross-industry generality) and should be framed as such, not hidden.
