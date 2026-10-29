"""Pure test-only policy scenarios; never pays money or grants referral rewards."""
from team14_persistent import SimError,ident,amount
def simulate_introduction(introducer_role, introduced_role):
 """Describe one of the four teacher/student introduction directions.

 This is a role-matrix *simulation*, not a booking, permission grant,
 referral payout, or approval of any commercial policy.
 """
 if (type(introducer_role) is not str or type(introduced_role) is not str
     or introducer_role not in ("teacher", "student")
     or introduced_role not in ("teacher", "student")):
  raise SimError('VALIDATION_ERROR','teacher/student introduction roles required')
 return dict(introducer_role=introducer_role,
             introduced_role=introduced_role,
             scenario_id=introducer_role+'_introduces_'+introduced_role,
             status='simulation_only',real_money=False,
             payment_enabled=False,policy_approved=False)

def simulate_referral(gross_krw,edges,depth_rates_bps=(300,),commission_bps=2000):
 amount(gross_krw,True)
 if type(commission_bps)!=int or not 0<=commission_bps<=10000:raise SimError('VALIDATION_ERROR','commission')
 if not isinstance(edges,(list,tuple)) or not isinstance(depth_rates_bps,(list,tuple)) or len(depth_rates_bps)>10:raise SimError('VALIDATION_ERROR','policy')
 if any(type(r)!=int or not 0<=r<=10000 for r in depth_rates_bps) or sum(depth_rates_bps)+commission_bps>10000:raise SimError('VALIDATION_ERROR','rates exceed gross')
 if not isinstance(edges,(list,tuple)) or len(edges)>10000:
  raise SimError('VALIDATION_ERROR','referral edges must be a bounded list')
 graph={}
 for edge in edges:
  if not isinstance(edge,(list,tuple)) or len(edge)!=2:
   raise SimError('VALIDATION_ERROR','referral edge must contain two IDs')
  child,parent=edge;ident(child);ident(parent)
  if child==parent or child in graph:raise SimError('CONFLICT','self or duplicate referral')
  graph[child]=parent
 # Every vertex is resolved at most once, including paths that are
 # unrelated to the student receiving the simulated referral award.
 resolved=set()
 for node in graph:
  if node in resolved:continue
  visiting=set();cur=node
  while cur in graph and cur not in resolved:
   if cur in visiting:raise SimError('CONFLICT','referral cycle')
   visiting.add(cur);cur=graph[cur]
  resolved.update(visiting)
 teacher=gross_krw*(10000-commission_bps-sum(depth_rates_bps))//10000
 rewards=[gross_krw*r//10000 for r in depth_rates_bps]
 platform=gross_krw-teacher-sum(rewards)
 return dict(gross=gross_krw,teacher=teacher,rewards=rewards,platform=platform,real_money=False,policy_approved=False,payment_enabled=False)
