# function_app.py — Version B: Validation Function for Logic Apps + Service Bus workflow
#
# Role: HTTP-triggered function called by the Logic App as the first step of the
# expense approval workflow. Validates the incoming expense request and returns a
# consistent JSON response that the Logic App uses to branch (valid vs. invalid).
#
# Logic App architecture overview:
#   1. Logic App trigger: new message on Service Bus queue "expense-requests"
#   2. Logic App calls this function (POST /api/validate) with the message body
#   3. Logic App checks response body field "valid":
#      - false → publish to "expense-outcomes" topic with label "rejected", end
#      - true  → evaluate amount:
#          < 100  → auto-approve, publish to topic with label "approved"
#          >= 100 → send manager an HTTP+wait callback URL (Logic Apps built-in)
#                   On approval   → publish to topic with label "approved"
#                   On rejection  → publish to topic with label "rejected"
#                   On timeout    → publish to topic with label "escalated"
#   4. Logic App sends notification step (HTTP POST or email connector)
#
# Manager approval approach — HTTP webhook:
#   The Logic App uses the built-in "HTTP Webhook" action which sends the manager
#   a callback URL and pauses. The manager approves/rejects by calling that URL.
#   Timeout is configured on the Logic App action itself (not in this function).
#   The env variable APPROVAL_TIMEOUT_SECONDS is documented here for reference and
#   would be used if the Logic App is redesigned to call an Azure Function for timing.
#
# Service Bus env vars (EXPENSE_QUEUE_NAME, OUTCOME_TOPIC_NAME,
# SERVICE_BUS_CONNECTION_STRING) are consumed by the Logic App, not by this function.
# They are included in local.settings.example.json so the full configuration is
# documented in one place.

import json
import logging
import os

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

VALID_CATEGORIES = ["travel", "meals", "supplies", "equipment", "software", "other"]
REQUIRED_FIELDS = ["employee_name", "employee_email", "amount", "category", "description", "manager_email"]


@app.function_name(name="validate_expense_http")
@app.route(route="", methods=["POST"])
def validate_expense_http(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"valid": False, "error": "Request body must be valid JSON."}),
            status_code=400,
            mimetype="application/json",
        )

    missing = [
        f for f in REQUIRED_FIELDS
        if f not in body or body[f] is None or str(body[f]).strip() == ""
    ]
    if missing:
        logging.warning("Validation failed: missing fields: %s", missing)
        return func.HttpResponse(
            json.dumps({"valid": False, "data": body}),
            status_code=200,
            mimetype="application/json",
        )

    if body["category"] not in VALID_CATEGORIES:
        logging.warning("Validation failed: invalid category '%s'", body["category"])
        return func.HttpResponse(
            json.dumps({"valid": False, "data": body}),
            status_code=200,
            mimetype="application/json",
        )

    logging.info("Validation passed for employee: %s, amount: %s", body["employee_name"], body["amount"])

    # TODO: Wire in Service Bus message send here if this function is refactored to
    # enqueue directly instead of relying on the Logic App trigger from the queue.
    # For now the Logic App reads this response and enqueues to expense-outcomes itself.

    return func.HttpResponse(
        json.dumps({"valid": True, "data": body}),
        status_code=200,
        mimetype="application/json",
    )
