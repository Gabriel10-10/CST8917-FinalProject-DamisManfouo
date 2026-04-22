# Final Project: Dual Implementation of an Expense Approval Workflow

**Name:** Damis Gabriel Manfouo
**Student Number:** [STUDENT_NUMBER_PLACEHOLDER]
**Course:** CST8917 — Serverless Applications | Algonquin College
**Project Title:** Compare & Contrast — Azure Durable Functions vs. Logic Apps + Service Bus
**Date:** [DATE_PLACEHOLDER]

---

## Version A — Azure Durable Functions

<!-- TODO: Replace these placeholder paragraphs with your own 2-3 paragraph summary after building Version A. -->

<!-- Paragraph 1: Briefly describe what you built. What is the overall architecture? Which functions did you implement (client, orchestrator, activities)? How did they connect together? -->

[Version A summary placeholder — describe the overall architecture and what you implemented.]

<!-- Paragraph 2: Explain your key design decisions. Why did you structure the orchestrator the way you did? How did you implement the Human Interaction pattern and durable timer? What tradeoffs did you make? -->

[Version A design decisions placeholder — explain the choices you made and why.]

<!-- Paragraph 3: What challenges did you run into? How did you debug or resolve them? What would you do differently? -->

[Version A challenges placeholder — reflect on what was hard and what you learned.]

---

## Version B — Azure Logic Apps + Service Bus

<!-- TODO: Replace these placeholder paragraphs with your own 2-3 paragraph summary after building Version B. -->

<!-- Paragraph 1: Describe the overall architecture. What Azure services did you use and how do they fit together (Logic App, validation Function, Service Bus queue, topic, subscriptions)? -->

[Version B summary placeholder — describe the overall architecture.]

<!-- Paragraph 2: Focus specifically on how you handled the manager approval step. The approach used here is an HTTP webhook: the Logic App uses an "HTTP and wait" action that sends the manager a callback URL; the manager approves or rejects by calling that URL. Explain why you chose this approach and how it differs from Durable Functions' external event mechanism. -->

[Version B manager approval approach placeholder — explain the webhook approach and your reasoning.]

<!-- Paragraph 3: What challenges did you face with the visual/declarative approach? How did you test it? What was easier or harder compared to Version A? -->

[Version B challenges placeholder — reflect on what was hard and what you learned.]

<!-- CHALLENGE TO DOCUMENT: Logic Apps rejects Azure Functions that use a custom route.
     The fix is to combine @app.function_name(name="...") with @app.route(route="", methods=["POST"]).
     Setting route="" (empty string) — NOT omitting the parameter, NOT route="some-name" — is what
     Logic Apps accepts. Any other route value triggers: "InvalidFunctionRoute: The function cannot
     be called from a logic app. It must not have a custom route."
     Include this in your challenges paragraph — it is a non-obvious Python v2 model constraint
     that is not clearly documented by Microsoft. -->

---

## Comparison Analysis

<!-- TODO: Fill in after building both versions. Target: 800-1200 words total across all six dimensions. -->
<!-- Be specific. "X was easier" is weak. Describe what you actually experienced and why it mattered. -->

### 1. Development Experience

<!-- Which was faster to build? Easier to debug? Which gave you more confidence the logic was correct? -->

- [Your observation here]
- [Your observation here]

### 2. Testability

<!-- Which was easier to test locally? Could you write automated tests for either? -->

- [Your observation here]
- [Your observation here]

### 3. Error Handling

<!-- How does each handle failures? Which gives more control over retries and recovery? -->

- [Your observation here]
- [Your observation here]

### 4. Human Interaction Pattern

<!-- How did each handle "wait for manager approval"? Which was more natural? -->

- [Your observation here]
- [Your observation here]

### 5. Observability

<!-- Which made it easier to monitor runs and diagnose problems? -->

- [Your observation here]
- [Your observation here]

### 6. Cost

<!-- Estimate cost at ~100 expenses/day and ~10,000 expenses/day. Use the Azure Pricing Calculator and state your assumptions. -->

- [Your cost estimate here]
- [Your assumptions here]

---

## Recommendation

<!-- TODO: Fill in after completing the comparison. Target: 200-300 words. -->
<!-- If a team asked you to build this for production, which approach would you choose and why? When would you choose the other instead? -->

[Recommendation placeholder]

---

## References

<!-- List all sources with working hyperlinks. Format: Author Last, First. "Title." Publisher, Year. URL -->

- [Format example: Microsoft. "Durable Functions overview." Microsoft Learn, 2024. https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview]

---

## AI Disclosure

Claude Code was used to scaffold the repository structure and generate initial function implementations. All logic was reviewed, tested, and modified by the student.
