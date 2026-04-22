# Final Project: Dual Implementation of an Expense Approval Workflow

**Name:** Damis Gabriel Manfouo
**Student Number:** 041204270
**Course:** CST8917 — Serverless Applications | Algonquin College
**Project Title:** Compare & Contrast — Azure Durable Functions vs. Logic Apps + Service Bus
**Date:** April 21, 2026

---

## Version A — Azure Durable Functions

Version A implements the expense approval workflow using Azure Durable Functions with the Python v2 programming model. The architecture consists of six functions: an HTTP client trigger (`expense_client`) that accepts incoming requests and starts the orchestration, an orchestrator (`expense_orchestrator`) that chains all steps, three activity functions (`validate_expense`, `process_expense`, `notify_employee`), and a second HTTP trigger (`manager_response`) that allows the manager to submit their decision. The client validates the request shape upfront and returns a 400 error for invalid input before starting the orchestration and returning a status check URL. All activities are called sequentially using `yield`, which ensures the deterministic replay that Durable Functions requires.

The central design decision was implementing the Human Interaction pattern by racing a durable timer against an external event. After routing an expense to manager review, the orchestrator calls `context.task_any([approval_task, timer_task])`, where `approval_task` waits for a `ManagerDecision` external event and `timer_task` is a durable timer set to `APPROVAL_TIMEOUT_SECONDS`. If the manager responds in time, the timer is cancelled and the decision is applied. If the timer fires first, the status is set to `escalated`. This race pattern expresses the intent clearly to any developer reading the code. Employee notifications are delivered via Azure Communication Services Email using the `EmailClient` SDK, which required provisioning two Azure resources: an Email Communication Services resource for the sending domain and a Communication Services resource for the connection string.

The most significant challenges in Version A were package naming and orchestrator discipline. The correct PyPI package is `azure-functions-durable`, not `azure-durable-functions`, and using the wrong name caused a silent import failure. The orchestrator also requires strict rules: no `datetime.now()`, no logging inside the orchestrator body, and no direct I/O, since any of these break deterministic replay. The subtlest runtime bug was that `approval_task.result` returns a JSON string rather than a parsed dict, causing a `'str' object has no attribute 'get'` error. The fix was to check `isinstance(manager_decision, str)` and parse with `json.loads()` before reading the decision field. Additionally, the `extensionBundle` block is required in `host.json` for durable bindings to register — omitting it produces a misleading error about unregistered bindings.

---

## Version B — Azure Logic Apps + Service Bus

Version B implements the same workflow using a visual Logic App (Consumption tier) triggered by an Azure Service Bus queue. When a request is submitted, the message is sent to the `expense-requests` queue via the Service Bus REST API with an Azure AD Bearer token. The Logic App picks up the message, decodes the base64 content using a Compose step (`base64ToString(triggerBody()?['ContentData'])`), and calls a lightweight Azure Function (`validate_expense_http`) that returns `{"valid": true/false, "data": {...}}`. A Parse JSON step extracts the response schema, and a second Compose step isolates the `data` object so individual fields like `employee_email` and `amount` are accessible as expressions throughout the workflow. Outcomes are published to an `expense-outcomes` Service Bus topic with `approved`, `rejected`, and `escalated` subscriptions, and employees are notified by email through the Office 365 Outlook connector.

Manager approval uses the built-in **Send Approval Email (V2)** action from the Office 365 Outlook connector, which sends the manager an email with Approve and Reject buttons and pauses the Logic App for up to a configurable timeout (PT2M for testing). If the manager responds, the `SelectedOption` output is evaluated by a Condition inside a Scope to route to the approved or rejected branch. If no response arrives within the timeout, the Scope is skipped entirely, and a Send message action configured with "run after: Scope is skipped" publishes the escalated outcome. This differs from Durable Functions, where the timer is a first-class durable entity that the orchestrator explicitly races against the external event. In Logic Apps, the timeout is a property of the email action itself and the escalation branch is wired through the "configure run after" mechanism rather than code.

Version B presented several non-obvious challenges. Logic Apps rejects Azure Functions that define a custom route: the Python v2 model requires combining `@app.function_name(name="...")` with `@app.route(route="", methods=["POST"])` — setting `route=""` (empty string) is the only value Logic Apps accepts, and this constraint is not clearly documented by Microsoft. The Service Bus trigger also delivers message content as base64, which caused the validation function to receive garbled input until a Compose decode step was added. Logic Apps' visual Condition designer treats all comparison values as strings, so comparing a JSON boolean `valid` to `"True"` (capital T) caused an `ActionFailed` error instead of a clean branch — the fix was to use `@equals(body('Parse_JSON')?['valid'], true)` with a lowercase boolean. Finally, the validation function originally returned no `data` field on failure, causing all downstream expressions to resolve to null. The function was updated to always return `data` regardless of the validation outcome.

---

## Comparison Analysis

### 1. Development Experience

Version A required more upfront setup — installing the correct package, configuring `host.json`, and understanding the orchestrator's replay constraints — but the workflow logic was expressed directly in Python with full IDE support and easy navigation between functions. The intent of the timer race was immediately readable as code. Version B was faster to get a first working run, but debugging was harder in practice. Wiring up the escalation branch required understanding the Scope container pattern, and small mistakes like a wrong boolean case produced cryptic `ActionFailed` errors rather than clear messages. Logic Apps felt faster for the happy path but slower when something went wrong.

### 2. Testability

Version A supports full local testing with `func start` and Azurite for storage emulation. All six scenarios in `test-durable.http` could be run entirely offline, including escalation by setting `APPROVAL_TIMEOUT_SECONDS=30`, and the activity functions could be unit tested independently of the orchestrator. Version B cannot be tested locally at all — every change required saving to Azure, waiting for the Logic App to pick up a Service Bus message, and inspecting the run history. The feedback loop was significantly slower, and the only locally testable component was the validation Azure Function.

### 3. Error Handling

Version A gives complete control through standard Python try/except. Retries, compensation logic, and partial failure recovery can all be expressed in code, and the orchestrator can catch activity failures and take alternate paths explicitly. Version B handles errors through "configure run after" settings on each action, where you specify whether an action should run after a predecessor succeeds, fails, times out, or is skipped. This works well for simple cases but becomes complex when multiple conditions interact, as experienced with the Scope and escalation branch. There is no equivalent of try/except for expressing recovery logic.

### 4. Human Interaction Pattern

Version A implements the Human Interaction pattern natively: `wait_for_external_event` suspends the orchestrator with zero resource consumption, and `create_timer` creates a durable checkpoint. The race between the two is a clean, testable pattern, and the manager submits a decision via a dedicated HTTP endpoint that raises the external event by instance ID. Version B handles manager approval through the Send Approval Email connector, which is easier to configure but less flexible. During testing, the Logic App response was noticeably faster — email notifications arrived almost instantly after the manager responded, whereas Durable Functions had a small but perceptible delay due to orchestration checkpointing overhead.

### 5. Observability

Version A integrates with Application Insights and provides structured logs from each activity. The orchestrator status API returns the current state, history, and output of any instance by ID, which made diagnosing the `json.loads()` bug straightforward. Version B provides a visual run history where every action shows its inputs, outputs, duration, and status. This was extremely useful for diagnosing the base64 decoding issue and the boolean comparison error without writing any additional logging code. For non-developers, Logic Apps observability is significantly more accessible.

### 6. Cost

**Assumptions:** Each expense request triggers one full workflow run with approximately 10–12 action executions. Email is sent via the Office 365 Outlook connector at no additional cost.

At **100 expenses/day**, both versions cost under $5/month. Durable Functions on the Consumption plan incurs negligible execution costs with small storage transaction charges for durable state. Logic Apps at $0.000025 per action × ~1,200 actions/day adds up to roughly $1/month, with Service Bus Standard tier adding ~$10/month.

At **10,000 expenses/day**, Durable Functions storage transaction costs grow to an estimated $15–30/month. Logic Apps reaches approximately $90/month in action execution costs alone, with Service Bus costs remaining fixed. At high volume, Durable Functions is more cost-efficient due to its consumption model versus Logic Apps' per-action pricing.

---

## Recommendation

For a team building this expense approval workflow in production today, Azure Logic Apps + Service Bus is the stronger choice for most scenarios. The built-in Send Approval Email connector eliminates the need to build a custom callback endpoint, the visual run history allows non-developers to monitor and diagnose runs without reading logs, and the Service Bus topic with subscriptions provides a clean integration point for downstream systems without additional code. The initial setup is faster and the workflow is auditable by anyone on the team regardless of coding background.

Azure Durable Functions becomes the better choice when the team is comfortable with Python, when the workflow logic is complex enough that the visual designer becomes a liability, or when local testability and CI/CD integration are non-negotiable requirements. Durable Functions also scales more cost-efficiently at high volumes due to its consumption-based model, and its Human Interaction pattern is more flexible — supporting custom approval UIs, multi-step approvals, or delegation workflows that the built-in connector cannot handle.

In short: Logic Apps for speed, simplicity, and accessibility; Durable Functions for control, testability, and scale.

---

## References

- Microsoft. "Durable Functions overview." Microsoft Learn, 2024. https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-overview
- Microsoft. "Human interaction in Durable Functions — Phone verification sample." Microsoft Learn, 2024. https://learn.microsoft.com/azure/azure-functions/durable/durable-functions-phone-verification
- Microsoft. "Azure Logic Apps overview." Microsoft Learn, 2024. https://learn.microsoft.com/azure/logic-apps/logic-apps-overview
- Microsoft. "Azure Service Bus messaging overview." Microsoft Learn, 2024. https://learn.microsoft.com/azure/service-bus-messaging/service-bus-messaging-overview
- Microsoft. "Azure Communication Services Email." Microsoft Learn, 2024. https://learn.microsoft.com/azure/communication-services/concepts/email/email-overview
- Microsoft. "Azure Functions Python developer guide." Microsoft Learn, 2024. https://learn.microsoft.com/azure/azure-functions/functions-reference-python

---

## AI Disclosure

Claude Code was used to scaffold the repository structure, assist with Logic App workflow design, and debug runtime errors throughout development. All logic was reviewed, tested, and modified by the student. The comparison analysis and reflection paragraphs reflect the student's direct experience building and testing both versions.
