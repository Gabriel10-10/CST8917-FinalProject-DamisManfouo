# function_app.py — Version A: Azure Durable Functions (Python v2 programming model)
# Implements the expense approval workflow using the Human Interaction pattern.
# Functions: expense_client (HTTP trigger), expense_orchestrator, validate_expense,
#            process_expense, notify_employee (activities), manager_response (HTTP trigger).

import logging
import json
import os
from datetime import timedelta

import azure.functions as func
import azure.durable_functions as df
from azure.communication.email import EmailClient

app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

VALID_CATEGORIES = ["travel", "meals", "supplies", "equipment", "software", "other"]
REQUIRED_FIELDS = ["employee_name", "employee_email", "amount", "category", "description", "manager_email"]


# ---------------------------------------------------------------------------
# HTTP Client — starts the orchestration
# ---------------------------------------------------------------------------

@app.route(route="expense", methods=["POST"])
@app.durable_client_input(client_name="client")
async def expense_client(req: func.HttpRequest, client) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body.", status_code=400)

    missing = [f for f in REQUIRED_FIELDS if f not in body or body[f] is None or str(body[f]).strip() == ""]
    if missing:
        return func.HttpResponse(
            json.dumps({"error": f"Missing required fields: {', '.join(missing)}"}),
            status_code=400,
            mimetype="application/json",
        )

    if body["category"] not in VALID_CATEGORIES:
        return func.HttpResponse(
            json.dumps({"error": f"Invalid category '{body['category']}'. Valid: {VALID_CATEGORIES}"}),
            status_code=400,
            mimetype="application/json",
        )

    instance_id = await client.start_new("expense_orchestrator", client_input=body)
    response = client.create_check_status_response(req, instance_id)
    return response


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@app.orchestration_trigger(context_name="context")
def expense_orchestrator(context: df.DurableOrchestrationContext):
    expense = context.get_input()

    validation_result = yield context.call_activity("validate_expense", expense)
    if not validation_result["valid"]:
        yield context.call_activity("notify_employee", {
            "expense": expense,
            "status": "rejected",
            "reason": validation_result["error"],
        })
        return {"status": "rejected", "reason": validation_result["error"]}

    routing = yield context.call_activity("process_expense", expense)

    if routing["decision"] == "auto_approved":
        notification = yield context.call_activity("notify_employee", {
            "expense": expense,
            "status": "approved",
            "reason": "Amount under $100 — auto-approved.",
        })
        return {"status": "approved", "notification": notification}

    # Human Interaction pattern: race a timer against the manager's decision.
    timeout_seconds = int(os.environ["APPROVAL_TIMEOUT_SECONDS"])
    deadline = context.current_utc_datetime + timedelta(seconds=timeout_seconds)

    approval_task = context.wait_for_external_event("ManagerDecision")
    timer_task = context.create_timer(deadline)

    winner = yield context.task_any([approval_task, timer_task])

    if winner == timer_task:
        # Timer fired first — no manager response received.
        timer_task.cancel() if not timer_task.is_completed else None
        final_status = "escalated"
        reason = "No manager response within the timeout period. Auto-approved and flagged as escalated."
    else:
        timer_task.cancel()
        manager_decision = approval_task.result
        if isinstance(manager_decision, str):
            manager_decision = json.loads(manager_decision)
        final_status = manager_decision.get("decision", "approved")
        reason = f"Manager decision: {final_status}."

    notification = yield context.call_activity("notify_employee", {
        "expense": expense,
        "status": final_status,
        "reason": reason,
    })
    return {"status": final_status, "reason": reason, "notification": notification}


# ---------------------------------------------------------------------------
# Activity: validate_expense
# ---------------------------------------------------------------------------

@app.activity_trigger(input_name="expense")
def validate_expense(expense: dict) -> dict:
    missing = [f for f in REQUIRED_FIELDS if f not in expense or str(expense[f]).strip() == ""]
    if missing:
        return {"valid": False, "error": f"Missing required fields: {', '.join(missing)}"}

    if expense["category"] not in VALID_CATEGORIES:
        return {"valid": False, "error": f"Invalid category '{expense['category']}'. Valid: {VALID_CATEGORIES}"}

    return {"valid": True}


# ---------------------------------------------------------------------------
# Activity: process_expense
# ---------------------------------------------------------------------------

@app.activity_trigger(input_name="expense")
def process_expense(expense: dict) -> dict:
    amount = float(expense["amount"])
    if amount < 100:
        return {"decision": "auto_approved"}
    return {"decision": "pending_manager"}


# ---------------------------------------------------------------------------
# Activity: notify_employee
# ---------------------------------------------------------------------------

@app.activity_trigger(input_name="payload")
def notify_employee(payload: dict) -> dict:
    expense = payload["expense"]
    status = payload["status"]
    reason = payload.get("reason", "")

    subject = f"Expense Request {status.title()} — {expense['category']} ${expense['amount']}"
    body = (
        f"Hi {expense['employee_name']},\n\n"
        f"Your expense request for ${expense['amount']} ({expense['category']}) has been {status}.\n"
        f"Reason: {reason}\n\n"
        f"Description: {expense['description']}"
    )

    notification = {
        "to": expense["employee_email"],
        "subject": subject,
        "body": body,
        "status": status,
    }

    connection_string = os.environ["ACS_CONNECTION_STRING"]
    from_email = os.environ["ACS_FROM_EMAIL"]

    message = {
        "senderAddress": from_email,
        "recipients": {"to": [{"address": expense["employee_email"]}]},
        "content": {"subject": subject, "plainText": body},
    }

    try:
        client = EmailClient.from_connection_string(connection_string)
        poller = client.begin_send(message)
        result = poller.result()
        notification["email_message_id"] = result.get("id")
        logging.info("Email sent to %s — message id %s", expense["employee_email"], result.get("id"))
    except Exception as exc:
        logging.error("Azure Communication Services email failed: %s", exc)
        notification["email_error"] = str(exc)

    return notification


# ---------------------------------------------------------------------------
# HTTP Trigger — manager submits approval/rejection decision
# ---------------------------------------------------------------------------

@app.route(route="expense/{instanceId}/respond", methods=["POST"])
@app.durable_client_input(client_name="client")
async def manager_response(req: func.HttpRequest, client) -> func.HttpResponse:
    instance_id = req.route_params.get("instanceId")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body.", status_code=400)

    decision = body.get("decision", "").lower()
    if decision not in ("approved", "rejected"):
        return func.HttpResponse(
            json.dumps({"error": "Field 'decision' must be 'approved' or 'rejected'."}),
            status_code=400,
            mimetype="application/json",
        )

    status = await client.get_status(instance_id)
    if status is None:
        return func.HttpResponse(
            json.dumps({"error": f"Orchestration instance '{instance_id}' not found."}),
            status_code=404,
            mimetype="application/json",
        )

    # Event name must exactly match what the orchestrator calls wait_for_external_event("ManagerDecision").
    await client.raise_event(instance_id, "ManagerDecision", {"decision": decision})

    return func.HttpResponse(
        json.dumps({"message": f"Decision '{decision}' sent to instance '{instance_id}'."}),
        status_code=200,
        mimetype="application/json",
    )
