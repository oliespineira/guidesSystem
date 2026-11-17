from app.db import Connection
from fastapi import APIRouter, Depends

from app.actas import tesoreria
from app.actas.policies import ApprovalPolicy, get_policy
from app.actas.schemas import BudgetCreate, RequestAction, RequestCreate, RequestPayment
from app.api_models import ERROR_RESPONSES
from app.db import get_db
from app.messaging.notifier import Notifier
from app.messaging.routes import get_notifier

router = APIRouter(prefix="/api/actas", tags=["tesoreria"], responses=ERROR_RESPONSES)


@router.post("/budgets", status_code=201)
def create_budget(body: BudgetCreate, conn: Connection = Depends(get_db)):
    return {"id": tesoreria.create_budget(conn, body.ronda_id, body.category, body.allocated_cents)}


@router.get("/budgets")
def list_budgets(ronda_id: int, conn: Connection = Depends(get_db)):
    return tesoreria.list_budgets(conn, ronda_id)

@router.get("/treasury")
def treasury(ronda_id: int, conn: Connection = Depends(get_db)):
    return tesoreria.treasury_info(conn, ronda_id)

@router.get("/requests")
def list_requests(ronda_id: int, conn: Connection = Depends(get_db)):
    return tesoreria.list_requests(conn, ronda_id)


@router.post("/requests/{request_id}/approve")
def approve(request_id: int, body: RequestAction, conn: Connection = Depends(get_db), notifier: Notifier = Depends(get_notifier)):
    tesoreria.Approve(request_id, body.volunteer_id, body.note).execute(conn, notifier)
    return {"id": request_id, "status": "approved"}


@router.post("/requests/{request_id}/reject")
def reject(request_id: int, body: RequestAction, conn: Connection = Depends(get_db), notifier: Notifier = Depends(get_notifier)):
    tesoreria.Reject(request_id, body.volunteer_id, body.note).execute(conn, notifier)
    return {"id": request_id, "status": "rejected"}


@router.post("/requests/{request_id}/pay")
def pay(request_id: int, body: RequestPayment, conn: Connection = Depends(get_db), notifier: Notifier = Depends(get_notifier)):
    tesoreria.MarkPaid(request_id, body.payment_ref, body.volunteer_id, body.note).execute(conn, notifier)
    return {"id": request_id, "status": "paid"}


@router.get("/requests/{request_id}/history")
def history(request_id: int, conn: Connection = Depends(get_db)):
    return tesoreria.request_history(conn, request_id)

@router.post("/budgets/{budget_id}/requests", status_code=201)
def submit_request(budget_id: int, body: RequestCreate,
                   conn: Connection = Depends(get_db),
                   policy: ApprovalPolicy = Depends(get_policy),
                   notifier: Notifier = Depends(get_notifier)):
    r = tesoreria.submit_request(conn, budget_id, body.rama, body.item, body.amount_cents, policy, notifier)
    return {"id": r.request_id, "status": r.verdict.status, "reason": r.verdict.reason, "similar": r.similar}