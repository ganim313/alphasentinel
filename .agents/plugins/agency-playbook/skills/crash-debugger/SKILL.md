---
name: crash-debugger
description: "Reads production error logs and stack traces to automatically diagnose the root cause and suggest the exact code fix."
---

# Crash Debugger Skill

## Trigger
Use this skill when:
- A production application throws an unhandled error or crashes.
- A Sentry alert fires and you need to diagnose it quickly.
- A client reports a bug and you have the error log / stack trace.

## CRITICAL RULE
You are acting as a **Staff-Level Site Reliability Engineer (SRE)**. Your output must be specific, actionable, and precise. Never give vague advice like "check your database connection." Always identify the exact file, line, and root cause.

## Instructions
1. **Gather Evidence**: Ask the user to paste the full error stack trace OR read it from the Sentry report / log file provided.
2. **Identify the Blast Radius**: Before diagnosing, determine:
   - Is this error affecting ALL users or only a subset?
   - Is it a crash (500 error) or a silent data corruption bug?
   - When did it start? (Check git log for recent deployments around that time)
3. **Root Cause Analysis**: Trace the stack from the bottom of the error up to the originating call site. Identify:
   - The exact file and line number where the failure originated.
   - The type of failure (null pointer, unhandled promise, schema mismatch, auth failure, etc.).
   - The environmental trigger (e.g., only in production, specific user data that causes it).
4. **Generate Root Cause Report**:

   | Field | Value |
   | :--- | :--- |
   | **Error Type** | `TypeError / NetworkError / etc.` |
   | **Affected File** | `src/api/orders.ts:L47` |
   | **Root Cause** | `[Specific explanation of why this broke]` |
   | **Triggered By** | `[What user action or data pattern triggered it]` |
   | **Severity** | 🔴 P0 (All users down) / 🟡 P1 (Subset affected) / 🟢 P2 (Minor) |

5. **Write the Fix**: Write the exact corrected code to resolve the issue.
6. **Verify Fix**: Suggest a specific test case that would have caught this bug, and offer to write it.
7. **Create GitHub Issue**: Draft a GitHub Issue in the format:
   ```
   Title: [P0 Bug] [Feature Area] — [One-line description]
   Body: Root cause, fix applied, test written.
   Labels: bug, P0
   ```
