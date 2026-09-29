---
template_id: "04"
phase: 3
assigned_role: "02_solutions_architect"
context_from: ["03_requirements_engineering.md"]
outputs_to: ["05_technical_sdlc_execution.md"]
status: template
---
# Template 04: System Design & Architecture (HLD & LLD)

**Purpose:** Creating the engineering blueprint before coding. This prevents architectural rewrites midway through the project.

---

## 1. High-Level Design (HLD)
* **Architecture Style:** [e.g., Monolithic, Microservices, Serverless].
* **System Diagram:** Provide a visual diagram mapping the interactions between:
  - The Client (Web/Mobile)
  - The API Gateway / Backend Servers
  - The Database
  - External Services (e.g., Cloudinary for images, Stripe for payments, Firebase for notifications).
* **Technology Decision Record (TDR) & Trade-Off Matrix:**
  *(CRITICAL: Run `@tech-stack-adviser.md` to debate and justify these technology choices across Velocity, Cost, Complexity, and Scalability. Do not skip.)*

  | Component Layer | Selected Technology | Alternative Evaluated | Why Selected (Velocity / Cost / Scalability) | Trade-Off Accepted |
  | :--- | :--- | :--- | :--- | :--- |
  | **Frontend Client** | `[e.g., Next.js 15]` | `[e.g., Vite SPA]` | `[SSR for SEO, rapid server actions]` | `[Higher mental model than basic SPA]` |
  | **Backend & API** | `[e.g., Node / Express / Route Handlers]` | `[e.g., Python FastAPI / Go]` | `[Full-stack TS type sharing]` | `[Single-threaded async event loop]` |
  | **Database Layer** | `[e.g., PostgreSQL via Supabase]` | `[e.g., MongoDB / MySQL]` | `[Relational integrity + RLS security]` | `[Strict schema migration discipline]` |
  | **Auth & Security** | `[e.g., Supabase Auth / NextAuth]` | `[e.g., Custom JWT + Redis]` | `[Pre-built OAuth + Session handling]` | `[Vendor abstraction layer]` |
  | **Hosting & Cloud** | `[e.g., Vercel + Managed DB]` | `[e.g., AWS ECS / VPS]` | `[Zero DevOps overhead for solo shipping]` | `[Serverless function execution timeouts]` |

## 2. Database Design (Entity-Relationship Diagram)
*(CRITICAL: You MUST write a `mermaid` code block containing the exact ERD for every single table in the database, including all columns and data types. Do NOT skip any tables.)*

* **Mermaid ERD:**
* **Row Level Security (RLS) / Auth Rules:** (Define who can read/write to each table).
* **Indexes:** (Define specific columns that need indexes for performance).

## 3. API Contracts (Swagger / OpenAPI representation)
*(CRITICAL: You MUST generate a detailed table for EVERY single API route. Do not summarize.)*

| Method | Endpoint Route | Request Payload | Response (Success) | Error States |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/resource` | `{"id": "string", "count": "number"}` | `200 OK: {"status": "success"}` | `400 Bad Request, 401 Unauthorized` |

## 4. State Management & Frontend Architecture
* How will global UI state be handled? (e.g., React Context, Redux, Zustand).
* How will server-state be cached? (e.g., React Query, SWR).---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 architectural trade-offs and wait for the human lead's explicit approval before proceeding to implementation.)*

* **Key Decision 1 (Tech Stack Selection):** `[Primary Frameworks chosen & justified: e.g., Next.js + Tailwind + Supabase Postgres]`
* **Key Decision 2 (Data Modeling & DB Choice):** `[Database type, indexing strategy, and multi-tenant RLS isolation approach]`
* **Key Decision 3 (Hosting & Infrastructure Cost):** `[Target cloud provider and projected monthly hosting cost ($/mo)]`

* **Human Lead Sign-Off:** ⏳ Awaiting Approval / ✅ Approved / 🔄 Revisions Requested
* **Human Overrides / Adjustments:** `[Type 'Approved' or enter adjustments]`

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Deliverable has been reviewed against requirements.
- [ ] No placeholder blocks (e.g. `[ ]`) remain unfilled.
- [ ] Human Lead has explicitly signed off above.
- [ ] Output complies with project_state.yml guidelines.

### Context Package for Next Agent
The following artifacts must be passed to the next phase:
- [ ] 04_system_design_architecture.md
