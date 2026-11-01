"""#128 isolated reconciliation of payment, refund, four-bucket ledger and payout statements.

All evidence is CALLER-SUPPLIED test data, NOT authenticated provider evidence.
Never invoke a payment provider or release real money. This model can identify
discrepancies, but a matching review is NOT a payout authorization.
"""
from collections import defaultdict

from team14_reversal_subledger import SimulatedReversalLedger
from team14_transaction_subledger import BUCKETS, MAX_KRW, _identifier


def _money(value, name):
    if type(value) is not int or value < 0 or value > MAX_KRW:
        raise ValueError("invalid " + name)
    return value


def _index(rows, *, fields, id_field, amount_fields):
    if type(rows) is not list or len(rows) > 1000:
        raise ValueError("expected bounded list of statements")
    indexed = {}
    for row in rows:
        if type(row) is not dict or set(row) != set(fields):
            raise ValueError("invalid statement schema")
        for field in fields:
            if field in amount_fields:
                _money(row[field], field)
            else:
                _identifier(row[field], field)
        key = row[id_field]
        if key in indexed:
            raise ValueError("duplicate statement id")
        indexed[key] = row
    return indexed


def reconcile_review_statements(*, ledger, payments, refunds, payouts):
    """Read immutable #114/#115 simulated entries; return a fail-closed review.

    payments: [{tx_id,evidence_id,amount_krw}]
    refunds: [{reversal_id,tx_id,evidence_id,amount_krw}]
    payouts: [{tx_id,teacher_net_krw}]
    Exact sets are required: missing, unknown and conflicting entries all HOLD.
    There is deliberately no method here that releases a payment or payout.
    """
    if type(ledger) is not SimulatedReversalLedger:
        raise ValueError("isolated reversal ledger required")
    pay = _index(payments, fields=("tx_id", "evidence_id", "amount_krw"),
                 id_field="tx_id", amount_fields={"amount_krw"})
    ref = _index(refunds, fields=("reversal_id", "tx_id", "evidence_id",
                                  "amount_krw"), id_field="reversal_id",
                 amount_fields={"amount_krw"})
    out = _index(payouts, fields=("tx_id", "teacher_net_krw"),
                 id_field="tx_id", amount_fields={"teacher_net_krw"})

    # One consistent SQLite snapshot. Only SELECTs; never writes to the ledger.
    db = ledger.db
    db.execute("BEGIN")
    try:
        transactions = {
            row["tx_id"]: dict(row)
            for row in db.execute("SELECT tx_id,evidence_id,gross_krw FROM sim_tx")
        }
        originals = defaultdict(dict)
        for row in db.execute("SELECT tx_id,bucket,amount_krw FROM sim_entry"):
            originals[row["tx_id"]][row["bucket"]] = row["amount_krw"]
        reversals = {
            row["reversal_id"]: dict(row)
            for row in db.execute(
                "SELECT reversal_id,tx_id,evidence_id,refund_krw FROM sim_reversal")
        }
        reversal_buckets = defaultdict(lambda: defaultdict(int))
        reversal_entries = defaultdict(dict)
        for row in db.execute(
                "SELECT r.tx_id,e.reversal_id,e.bucket,e.reversed_krw "
                "FROM sim_reversal_entry e "
                "JOIN sim_reversal r ON r.reversal_id=e.reversal_id"):
            reversal_buckets[row["tx_id"]][row["bucket"]] += row["reversed_krw"]
            reversal_entries[row["reversal_id"]][row["bucket"]] = row["reversed_krw"]
        # Inspect orphan rows inside the same read-only snapshot. An inner JOIN
        # alone silently drops unparented buckets and can falsely MATCH.
        orphan_entry_ids = {
            row["reversal_id"] for row in db.execute(
                "SELECT e.reversal_id FROM sim_reversal_entry e "
                "LEFT JOIN sim_reversal r ON r.reversal_id=e.reversal_id "
                "WHERE r.reversal_id IS NULL")
        }
    finally:
        db.execute("ROLLBACK")

    failures = set()
    # Reject parentless ledger evidence even if amounts appear balanced.
    # No real-money or operating DB path is touched by this review.
    for reversal_id, source in reversals.items():
        if source["tx_id"] not in transactions:
            failures.add("ORPHAN_REVERSAL_TRANSACTION:" + reversal_id)
    for reversal_id in orphan_entry_ids:
        failures.add("ORPHAN_REVERSAL_ENTRY:" + reversal_id)
    # Aggregate conservation alone is insufficient: a forged/incomplete
    # reversal can sum to its refund while omitting required bucket entries.
    # Validate EACH immutable reversal's four-bucket shape before reporting
    # a matched review. No financial release is ever authorized.
    for reversal_id, source in reversals.items():
        entries = reversal_entries.get(reversal_id, {})
        if (set(entries) != set(BUCKETS)
                or sum(entries.values()) != source["refund_krw"]):
            failures.add("REVERSAL_ENTRY_MISMATCH:" + reversal_id)
    for tx_id in sorted(set(transactions) | set(pay) | set(out)):
        source = transactions.get(tx_id)
        if source is None:
            failures.add("UNKNOWN_TRANSACTION:" + tx_id)
            continue
        payment = pay.get(tx_id)
        if payment is None:
            failures.add("MISSING_PAYMENT:" + tx_id)
        elif (payment["evidence_id"] != source["evidence_id"]
              or payment["amount_krw"] != source["gross_krw"]):
            failures.add("PAYMENT_MISMATCH:" + tx_id)

        buckets = originals.get(tx_id, {})
        if set(buckets) != set(BUCKETS) or sum(buckets.values()) != source["gross_krw"]:
            failures.add("LEDGER_MISMATCH:" + tx_id)
            continue
        reversed_by_bucket = reversal_buckets.get(tx_id, {})
        if (any(b not in BUCKETS for b in reversed_by_bucket)
                or any(reversed_by_bucket.get(b, 0) > buckets[b] for b in BUCKETS)):
            failures.add("REVERSAL_LEDGER_MISMATCH:" + tx_id)
            continue
        teacher_net = buckets["teacher"] - reversed_by_bucket.get("teacher", 0)
        statement = out.get(tx_id)
        if statement is None:
            failures.add("MISSING_PAYOUT_STATEMENT:" + tx_id)
        elif statement["teacher_net_krw"] != teacher_net:
            failures.add("PAYOUT_MISMATCH:" + tx_id)

    for reversal_id in sorted(set(reversals) | set(ref)):
        source = reversals.get(reversal_id)
        statement = ref.get(reversal_id)
        if source is None:
            failures.add("UNKNOWN_REFUND:" + reversal_id)
        elif statement is None:
            failures.add("MISSING_REFUND:" + reversal_id)
        elif any(statement[k] != source[original]
                 for k, original in (("tx_id", "tx_id"),
                                     ("evidence_id", "evidence_id"),
                                     ("amount_krw", "refund_krw"))):
            failures.add("REFUND_MISMATCH:" + reversal_id)

    for tx_id, source in transactions.items():
        total_refunded = sum(r["refund_krw"] for r in reversals.values()
                             if r["tx_id"] == tx_id)
        if (total_refunded > source["gross_krw"]
                or sum(reversal_buckets.get(tx_id, {}).values()) != total_refunded):
            failures.add("REVERSAL_TOTAL_MISMATCH:" + tx_id)

    return {
        "task": 128,
        "status": "DISCREPANCY_HOLD" if failures else "MATCHED_REVIEW_ONLY",
        "discrepancy_hold": bool(failures),
        "discrepancies": sorted(failures),
        "transactions_checked": len(transactions),
        "refunds_checked": len(reversals),
        "payout_hold": True,  # Always held: no authorized external proof/policy.
        "provider_provenance_verified": False,
        "operator_approval_verified": False,
        "payout_authorized": False,
        "real_money_enabled": False,
        "operating_db_connected": False,
        "external_api_called": False,
    }
