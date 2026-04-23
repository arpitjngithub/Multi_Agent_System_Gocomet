# PRD - GoComet Nova Trade Document Pipeline

## 1. Nova and GoComet Understanding

### What is Nova?
Nova is GoComet's agentic AI layer for logistics and trade operations. It is designed to deliver an outcome, not just another dashboard. Instead of asking an operator to monitor data, interpret it, and then take action manually, Nova is expected to understand the workflow, run the decisioning steps, and move the work forward. In the trade document case, the output is not "a page with extracted values." The output is a decision with supporting evidence: approve, flag, or request an amendment. That distinction matters because customs and cargo teams are not short on dashboards; they are short on time, consistency, and confidence under operational pressure.

### What is the FDE model?
The Forward Deployed Engineer model means GoComet does not treat implementation as a handoff after a sale. An engineer works closely with the customer, learns the real exceptions in the workflow, and shapes Nova around those operational details. That is a better fit than a standard implementation team because document validation rules vary by customer, lane, product category, and compliance sensitivity. The FDE closes the gap between product intent and messy reality, which is exactly where an agentic system succeeds or fails.

### What is a System of Outcomes?
A System of Outcomes is software that completes work with enough trust and traceability that a user can rely on the result. A System of Record stores data. A System of Engagement helps people collaborate around the work. Nova sits one level higher: it receives an input, applies reasoning, and returns an operationally useful result. In this workflow that means a shipment document enters the system and a clear next action comes out with reasoning, confidence, and an audit trail.

## 2. Problem Statement

Trade document validation breaks in five predictable places today. Operators read documents line by line, which is slow and inconsistent. Rules often live in tribal knowledge, so two operators may judge the same document differently. Supplier corrections happen through multi-cycle email loops that waste days. Low-confidence readings are easy to miss, which creates silent approval risk. Finally, there is usually no structured trace of what was checked, why a document failed, or who overrode the system.

Success in the first five minutes is simple and concrete. A CG operator uploads a document and gets structured output in under 30 seconds. Every required field is marked clearly as match, mismatch, or uncertain. The operator can understand the next action immediately without reopening the PDF. If the document is bad, the system surfaces the uncertainty instead of pretending confidence.

## 3. Users and Jobs To Be Done

### Persona 1 - CG Operator
The CG operator processes 50 to 200 documents each week and is accountable for speed, correctness, and exception handling. Their pain is repetitive checking, unclear auditability, and slow communication with suppliers when a document is wrong.

### Persona 2 - Supplier
The supplier submits shipping paperwork and is usually outside the internal process. Their pain is delayed feedback, vague rejection reasons, and repeated correction cycles caused by incomplete issue lists.

### JTBD
1. When I receive a new trade document, I want the system to extract key fields automatically so that I do not spend 15 to 20 minutes reading it manually.
2. When extraction completes, I want to see a field-by-field pass, fail, or uncertain status so that I know where to focus immediately.
3. When the system is unsure about a field, I want it called out explicitly so that I do not accidentally approve bad data.
4. When a required field mismatches the customer rule set, I want an amendment request drafted automatically so that I can shorten the correction loop with the supplier.
5. When I review an exception, I want to understand the agent's reasoning so that I can make a faster, defensible decision.
6. When a supplier sends a revised document, I want the pipeline to rerun consistently so that I can confirm the fix without redoing all prior work.

## 4. Agent Architecture

Three agents is the right boundary for this problem because the steps represent three distinct failure surfaces. The extractor handles perception. The validator handles rule-based reasoning. The router handles operational action. A single prompt would blur those responsibilities, make debugging hard, and allow a hallucination in extraction to contaminate the final action silently. Five or more agents would add orchestration overhead without creating a cleaner trust boundary for the first version.

The Extractor Agent accepts a PDF or image and returns structured JSON for eight required fields plus confidence per field. The Validator Agent accepts extracted JSON and a customer rule set, then returns field-level statuses and an overall summary. The Router Agent reads the validator output and produces a decision with reasoning and action items, plus a supplier amendment draft when needed.

Agents communicate through structured JSON persisted to a shared `pipeline_runs` record keyed by `document_id`. This gives each step a durable handoff. If the process crashes mid-run, the orchestrator can inspect persisted state and resume from the last completed stage instead of restarting from scratch.

## 5. LLM and Tooling Choices

For extraction, the best production option is a vision-capable model such as GPT-4o or Claude Sonnet with document understanding because trade documents arrive as PDFs, scans, and imperfect images. For the validator, a cheaper text model is sufficient because the work is deterministic comparison against a rule set. For the router, a small fast model is enough because the task is classification plus explanation.

For this POC, the backend uses FastAPI and SQLite because both keep the system portable and easy to demo on a laptop. The orchestrator is a small custom state machine rather than LangGraph. That choice keeps the execution path obvious in code and easier to explain in a DAW setting. Structured output is used for extraction and validation because those steps need predictable schemas. The router keeps structured fields for the decision and action items, but still returns human-readable reasoning.

## 6. Trust, Failure Handling, and Evals

Hallucination prevention starts at extraction. Every field includes confidence. If a field is unreadable or below the threshold, it becomes `uncertain` and cannot be silently approved downstream. The prompt for the vision model explicitly says to return `null` rather than guess. In the code path, the validator treats `null` or confidence below `0.7` as uncertain regardless of the rule.

The pipeline sets a clear trust policy: uncertainty routes to human review, required mismatches route to an amendment draft, and only strong matches are auto-approved. To avoid runaway behavior, the implementation uses a simple sequential orchestrator with bounded execution. In a production version, each LLM step would have at most two retries and per-document caching keyed by document hash.

Offline eval: a 20-document set with manually verified truth labels, measuring per-field extraction accuracy and mismatch detection quality. Online metric: percentage of documents that reach a correct final decision without human intervention in extraction or validation.

## 7. Metrics and Success Criteria

### North Star
Percentage of trade documents that reach a correct final decision without human intervention in extraction or validation.

### Supporting Metrics
1. Field extraction accuracy by field against ground truth
2. False approval rate on required mismatches
3. Percentage of uncertain fields surfaced instead of silently approved
4. Router decision accuracy against operator-confirmed outcome
5. Average end-to-end latency per document
6. Cost per processed document
7. Human override rate after a system recommendation
8. Supplier amendment acceptance rate

### Go / No-Go for a Two-Week Pilot
Go if extraction accuracy exceeds 85 percent on pilot documents, there are zero silent approvals on critical mismatches, latency stays under 45 seconds, and operators report that the system helps them act faster. No-Go if required mismatches slip through, latency regularly exceeds two minutes, or operators still need to re-read a large share of documents manually.

## 8. What's Next

The next highest-value step is email ingestion because it removes the manual upload step and makes the workflow feel truly agentic. Second is the supplier feedback loop so the system can send amendment drafts automatically and track replies. Third is a rule management UI so customer-specific logic can be updated without developer intervention. Those three features tighten the loop from document arrival to shipment-ready action, which is the real promise of Nova.
