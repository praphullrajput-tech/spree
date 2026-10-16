---
name: speckit-assist-ask0
description: Answer developer questions about features, architecture, and rationale
  using the specs directory and project constitution
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: assist:commands/speckit.assist.ask.md
---

# Ask Codebase Questions

Query the project's specification knowledge base to understand how features work, why architectural decisions were made, and where specific logic lives. This command reads from the existing `specs/` directory (both migrated and newly authored artifacts) and the `.specify/memory/constitution.md` to provide accurate, context-aware answers.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding. The user will provide a natural language question (e.g., "Why do we use Redis for the auth system?", "How does the payment retry mechanism work?", or "Where are the validation rules for user registration?").

## Prerequisites

1. Verify a spec-kit project exists by checking for the `.specify/` directory.
2. Verify the existence of `.specify/memory/constitution.md`.
3. Verify the `specs/` directory exists and contains feature subdirectories with `.md` artifacts.

## Outline

1. **Analyze the query**: Determine the core intent of the user's question:
* **"How"**: Requires looking at `spec.md` (requirements) and `plan.md` (implementation approach).
* **"Why"**: Requires looking at `.specify/memory/constitution.md` (project-wide rules/architecture) and `plan.md` (technical context/decisions).
* **"Where"**: Requires mapping components to the source codebase using `tasks.md` and module maps.



2. **Retrieve context**: Scan the knowledge base to find relevant information:
| Knowledge Source | What to look for |
| --- | --- |
| `specs/*/spec.md` | User scenarios, business requirements, success criteria, explicit assumptions |
| `specs/*/plan.md` | Architectural patterns, technical decisions, complexity assessments |
| `specs/*/tasks.md` | Component structures, file locations, gap analysis from migrated features |
| `.specify/memory/constitution.md` | Project-wide naming conventions, tech stack mandates, directory boundaries |



3. **Cross-reference code (Optional but recommended)**: Once relevant specs are identified, briefly map them to the actual source code to ensure the answer reflects the current state of the implementation.
4. **Synthesize the answer**: Formulate a comprehensive response that directly answers the user's question by combining insights from the constitution and the specific feature artifacts.
5. **Output format**:
    ```markdown
    # Answer: [Brief Summary of Topic]

    [Direct, clear answer to the user's question]

    ## Rationale & Architecture
    - Explain the "why" based on `constitution.md` or `plan.md`.
    - Highlight any specific architectural constraints that influenced this.

    ## Feature Details
    - Summarize the exact behavior defined in the relevant `spec.md`.
    - Mention if this feature was reverse-engineered (`status: migrated`) or originally specified via SDD.

    ## Sources Referenced
    - :page_facing_up: `specs/feature-name/spec.md` (Requirements)
    - :page_facing_up: `.specify/memory/constitution.md` (Architecture)

    ```





## Rules

* **Read-only** — this command never modifies any files or generates new artifacts.
* **Spec-first** — always prioritize the documentation found in `specs/` and `constitution.md` over guessing purely from the raw source code.
* **Cite your sources** — explicitly mention which files (e.g., `specs/auth/plan.md`) provided the information.
* **Acknowledge missing context** — if the answer cannot be found in the specs or constitution, clearly state that the rationale is undocumented before attempting to infer from the code.
* **Respect feature origins** — take note if a spec is marked `status: migrated` (meaning it was reverse-engineered and might contain identified "gaps") versus a natively planned Spec Kit feature.
