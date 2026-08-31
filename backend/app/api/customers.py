"""GET /customers, GET /customers/{id}/calls — reads only, no pipeline work here."""
from fastapi import APIRouter, HTTPException

from app.db.session import DbConn
from app.schemas.call import CallSummary, Customer

router = APIRouter()


@router.get("", response_model=list[Customer])
def list_customers(conn: DbConn):
    rows = conn.execute(
        """
        SELECT c.id, c.name,
               COUNT(calls.id)       AS call_count,
               MAX(calls.started_at) AS last_contact
        FROM customers c
        LEFT JOIN calls ON calls.customer_id = c.id
        GROUP BY c.id, c.name
        ORDER BY call_count DESC, c.name
        """
    ).fetchall()
    return [Customer(**dict(r)) for r in rows]


@router.get(
    "/{customer_id}/calls",
    response_model=list[CallSummary],
    responses={404: {"description": "No such customer"}},
)
def customer_calls(customer_id: str, conn: DbConn):
    exists = conn.execute(
        "SELECT 1 FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail=f"no such customer: {customer_id}")

    rows = conn.execute(
        """
        SELECT c.id, c.started_at, c.duration_seconds, c.intent_label,
               c.resolution_status, c.summary, c.attention_score,
               ROUND((SELECT AVG(verified) FROM evidence WHERE evidence.call_id = c.id) * 100, 1)
                   AS evidence_coverage
        FROM calls c
        WHERE c.customer_id = ?
        ORDER BY c.started_at DESC
        """,
        (customer_id,),
    ).fetchall()
    return [CallSummary(**dict(r)) for r in rows]
