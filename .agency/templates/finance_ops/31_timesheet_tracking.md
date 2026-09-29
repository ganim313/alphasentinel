---
template_id: "31"
phase: 7
assigned_role: "finance_ops/finance_strategist"
context_from: ["07_deployment_runbook.md"]
outputs_to: []
status: template
---
# Template 31: Timesheet & Billable Hours Tracking

**Purpose:** Accurate time tracking is the difference between a profitable project and a loss. This template tracks hours by phase and deliverable for invoicing and post-mortem analysis.

---

## 1. Project Budget Summary
| Field | Value |
| :--- | :--- |
| **Total Quoted** | `$0` |
| **Hourly Rate** | `$0/hr` |
| **Estimated Hours** | `0h` |
| **Logged Hours** | `0h` |
| **Remaining Budget** | `0h` |

## 2. Phase-by-Phase Hour Log

### Phase 1: Intake & Proposal
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Client discovery call | PM | 1.5 | Yes |
| YYYY-MM-DD | SOW drafting | PM | 2.0 | Yes |

### Phase 2: Requirements
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | PRD writing | PM | 4.0 | Yes |

### Phase 3: Architecture
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | ERD design | Architect | 3.0 | Yes |

### Phase 4: Implementation
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Auth system | Backend | 6.0 | Yes |
| YYYY-MM-DD | Dashboard UI | Frontend | 8.0 | Yes |

### Phase 5: Testing & Security
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | E2E test suite | QA | 5.0 | Yes |

### Phase 6: Deployment
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | CI/CD setup | DevOps | 3.0 | Yes |

### Phase 7: Handoff
| Date | Task | Role | Hours | Billable? |
| :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Documentation | Legal Ops | 2.0 | Yes |

## 3. Non-Billable Hours Log
| Date | Task | Reason | Hours |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Rework due to unclear requirements | Agency fault | 2.0 |

## 4. Invoice Reconciliation
- **Billable Total:** `0h × $0/hr = $0`
- **Non-Billable Total:** `0h` (write-off)
- ** vs. Original Quote:** `+/- $0` (over/under budget)

---

## ✍️ Human Lead Decision & Sign-Off Block
1. [ ] Approved — Hours accurate and ready for invoicing
2. [ ] Revisions Required

**Status:** ⏳ Awaiting Approval
