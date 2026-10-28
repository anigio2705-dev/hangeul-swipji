"""Pure test-only policy scenarios; never pays money or grants referral rewards."""
from team14_persistent import SimError,ident,amount
def simulate_referral(gross_krw,edges,depth_rates_bps=(300,),commission_bps=2000):
 amount(gross_krw,True)
 if type(commission_bps)!=int or not 0<=commission_bps<=10000:raise SimError('VALIDATION_ERROR','commission')
 if not isinstance(edges,(list,tuple)) or not isinstance(depth_rates_bps,(list,tuple)) or len(depth_rates_bps)>10:raise SimError('VALIDATION_ERROR','policy')
 if any(type(r)!=int or not 0<=r<=10000 for r in depth_rates_bps) or sum(depth_rates_bps)+commission_bps>10000:raise SimError('VALIDATION_ERROR','rates exceed gross')
 graph={}
 for child,parent in edges:
  ident(child);ident(parent)
  if child==parent or child in graph:raise SimError('CONFLICT','self or duplicate referral')
  graph[child]=parent
 for node in graph:
  seen={node};cur=node
  while cur in graph:
   cur=graph[cur]
   if cur in seen:raise SimError('CONFLICT','referral cycle')
   seen.add(cur)
 teacher=gross_krw*(10000-commission_bps-sum(depth_rates_bps))//10000
 rewards=[gross_krw*r//10000 for r in depth_rates_bps]
 platform=gross_krw-teacher-sum(rewards)
 return dict(gross=gross_krw,teacher=teacher,rewards=rewards,platform=platform,real_money=False,policy_approved=False,payment_enabled=False)
