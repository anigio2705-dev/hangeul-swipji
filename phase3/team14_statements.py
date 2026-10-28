"""Read-only simulated settlement statements; never exposes a payment operation."""
from team14_persistent import SimError,ident

def lesson_statement(store,month_id,lesson_id):
    ident(month_id);ident(lesson_id)
    row=store.db.execute(
        'SELECT id,booking_id,amount,state,refunded FROM lessons WHERE month_id=? AND id=?',
        (month_id,lesson_id)).fetchone()
    if row is None: raise SimError('NOT_FOUND','lesson not found')
    entries=[dict(transaction_id=r['transaction_id'],kind=r['kind'],amount_krw=r['amount'])
             for r in store.db.execute(
                 'SELECT transaction_id,kind,amount FROM ledger WHERE lesson_id=? ORDER BY id',
                 (lesson_id,))]
    by_kind={}
    for e in entries: by_kind[e['kind']]=by_kind.get(e['kind'],0)+e['amount_krw']
    teacher=by_kind.get('teacher_accrual',0)+by_kind.get('teacher_reversal',0)
    referral=by_kind.get('referral_accrual',0)+by_kind.get('referral_reversal',0)
    platform=by_kind.get('platform_remainder',0)+by_kind.get('platform_reversal',0)
    refunded=row['refunded'];gross=row['amount']
    pending=gross-refunded-teacher-referral-platform
    if min(teacher,referral,platform,pending)<0 or by_kind.get('refund_reversal',0)!=-refunded:
        raise AssertionError('lesson ledger conservation')
    return dict(month_id=month_id,lesson_id=lesson_id,booking_id=row['booking_id'],
                state=row['state'],gross_krw=gross,refunded_krw=refunded,
                teacher_krw=teacher,referral_krw=referral,platform_krw=platform,
                pending_krw=pending,ledger=entries,real_money=False,
                rates_approved=False)

def month_statement(store,month_id):
    ident(month_id)
    ids=[r['id'] for r in store.db.execute(
        'SELECT id FROM lessons WHERE month_id=? ORDER BY id',(month_id,))]
    if not ids: raise SimError('NOT_FOUND','month not found')
    lessons=[lesson_statement(store,month_id,i) for i in ids]
    totals=store.totals(month_id)
    for key,field in [('gross','gross_krw'),('refunded','refunded_krw'),
                      ('teacher','teacher_krw'),('referral','referral_krw'),
                      ('platform','platform_krw'),('pending','pending_krw')]:
        if totals[key]!=sum(x[field] for x in lessons):
            raise AssertionError('monthly statement mismatch')
    return dict(month_id=month_id,lessons=lessons,totals=totals,
                real_money=False,rates_approved=False)
