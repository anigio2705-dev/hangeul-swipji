"""Simulated referral eligibility. No approved reward rates or money transfers."""
from team14_persistent import SimError,ident,amount

def eligible_referral(gross_krw,student_id,edges,depth_rates_bps=(300,),commission_bps=2000):
    amount(gross_krw,True);ident(student_id)
    if type(commission_bps)!=int or not 0<=commission_bps<=10000:
        raise SimError('VALIDATION_ERROR','commission')
    if (not isinstance(edges,(list,tuple)) or len(edges)>10000
        or not isinstance(depth_rates_bps,(list,tuple)) or len(depth_rates_bps)>10):
        raise SimError('VALIDATION_ERROR','referral policy')
    if any(type(r)!=int or not 0<=r<=10000 for r in depth_rates_bps) or sum(depth_rates_bps)+commission_bps>10000:
        raise SimError('VALIDATION_ERROR','rates')
    graph={}
    for edge in edges:
        if not isinstance(edge,(list,tuple)) or len(edge)!=2:
            raise SimError('VALIDATION_ERROR','referral edge')
        child,parent=edge;ident(child);ident(parent)
        if child==parent or child in graph:
            raise SimError('CONFLICT','self or duplicate referral')
        graph[child]=parent
    # Validate each path once to avoid quadratic work on long chains.
    resolved=set()
    for node in graph:
        if node in resolved:continue
        visiting=set();cur=node
        while cur in graph and cur not in resolved:
            if cur in visiting:raise SimError('CONFLICT','referral cycle')
            visiting.add(cur);cur=graph[cur]
        resolved.update(visiting)
    recipients=[];cur=student_id;seen={cur}
    for rate in depth_rates_bps:
        parent=graph.get(cur)
        if parent is None:break
        if parent in seen:raise SimError('CONFLICT','referral cycle')
        recipients.append(dict(user_id=parent,amount_krw=gross_krw*rate//10000))
        seen.add(parent);cur=parent
    # Missing ancestors cannot receive rewards. Unallocated share stays with platform.
    teacher=gross_krw*(10000-commission_bps-sum(depth_rates_bps))//10000
    platform=gross_krw-teacher-sum(x['amount_krw'] for x in recipients)
    return dict(student_id=student_id,gross_krw=gross_krw,teacher_krw=teacher,
                recipients=recipients,platform_krw=platform,real_money=False,
                policy_approved=False,payment_enabled=False)
