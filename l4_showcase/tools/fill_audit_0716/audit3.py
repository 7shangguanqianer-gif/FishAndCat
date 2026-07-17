# -*- coding: utf-8 -*-
import re, json, sys
sys.path.insert(0, r'F:\abb_wh_work\sim')
sys.stdout.reconfigure(encoding="utf-8")
import warehouse_sim as ws

data = open(r'F:\abb_wh_work\l4_showcase\src\s3_fill_store.js', encoding='utf-8').read()
p = json.loads(re.search(r'/\*__S3_FILL_PAYLOAD_BEGIN__\*/(.*?)/\*__S3_FILL_PAYLOAD_END__\*/', data, re.S).group(1))
lanes = {l['algorithm']['id']: l for l in p['online_lanes']}
cat = {g['gid']: g for g in p['cargo_catalog']}

print("="*70)
print("C-recompute. Independently recompute expected_retrieval_s from placements")
print("="*70)
ws.ACCEL = True
for alg in ('seq','near','score'):
    lane=lanes[alg]
    placed=[]
    for e in lane['events']:
        c,t=e['decision']['selected_slot']; gid=e['gid']
        placed.append((cat[gid], c, t))
    fsum=sum(g['freq'] for g,_,_ in placed)
    exp=sum(g['freq']*ws.travel_time(c,t) for g,c,t in placed)/fsum
    stored=lane['metrics']['expected_retrieval_s']
    print(f"  {alg}: recompute exp_t={exp:.6f}  stored={stored:.6f}  match={abs(exp-stored)<1e-6}")

print("\n"+"="*70)
print("C-makespan. Why makespan identical: sum of per-slot cycle time (order-invariant)")
print("="*70)
for alg in ('seq','near','score'):
    lane=lanes[alg]
    slots=sorted(tuple(e['decision']['selected_slot']) for e in lane['events'])
    # cycle time per event = load + laden(0,0->slot) + store + empty_return(slot->0,0), independent of order & good weight? load/store depend on weight
    print(f"  {alg}: #distinct slot-multiset hash={hash(tuple(slots))}")
seqslots=sorted(tuple(e['decision']['selected_slot']) for e in lanes['seq']['events'])
nearslots=sorted(tuple(e['decision']['selected_slot']) for e in lanes['near']['events'])
scoreslots=sorted(tuple(e['decision']['selected_slot']) for e in lanes['score']['events'])
print(f"  seq slotset == near slotset == score slotset (all managed filled): {seqslots==nearslots==scoreslots}")
print("  -> makespan = sum of per-event durations; laden/empty travel depends only on slot;")
print("     load/store handle depends on good weight (same 267 goods). Total identical across lanes.")
# But handle_time depends on weight, and each good placed once in every lane -> sum handle identical. travel sum: same slot multiset -> identical.

print("\n"+"="*70)
print("Score margin on its OWN objective (fixed_score_diagnostic_total, lower=better)")
print("="*70)
d={alg:lanes[alg]['metrics']['fixed_score_diagnostic_total'] for alg in ('seq','near','score')}
print(f"  seq={d['seq']:.4f} near={d['near']:.4f} score={d['score']:.4f}")
print(f"  score vs seq: {100*(d['score']-d['seq'])/d['seq']:+.2f}%   score vs near: {100*(d['score']-d['near'])/d['near']:+.2f}%")

print("\n"+"="*70)
print("Checklist 6. PLC(uniform, xUseAccel=FALSE default) vs SHOWCASE(accel) travel divergence")
print("="*70)
def tt_uniform(c,t):
    ws.ACCEL=False; return ws.travel_time(c,t)
def tt_accel(c,t):
    ws.ACCEL=True; return ws.travel_time(c,t)
print(f"  t_max: uniform(ST FC_TMax)={tt_uniform(19,19):.4f}   accel(SIM t_max)={tt_accel(19,19):.4f}")
print(f"  {'slot':>10} {'uniform_s':>10} {'accel_s':>10} {'diff':>8} {'diff%':>7}")
for c,t in [(19,19),(0,19),(19,0),(5,11),(10,10),(0,6),(19,10)]:
    u=tt_uniform(c,t); a=tt_accel(c,t)
    dp = 100*(a-u)/u if u else 0
    print(f"  {str((c,t)):>10} {u:>10.4f} {a:>10.4f} {a-u:>8.4f} {dp:>6.1f}%")
# tNorm inconsistency on ST under accel: numerator accel / denominator uniform
worst_num=tt_accel(19,19); denom_uniform=tt_uniform(19,19)
print(f"\n  ST-under-accel tNorm at (19,19) = accel_numerator/uniform_FC_TMax = {worst_num:.4f}/{denom_uniform:.4f} = {worst_num/denom_uniform:.4f} (>1 => resv can go negative)")
print(f"  SIM tNorm at (19,19) = accel/accel = {worst_num:.4f}/{worst_num:.4f} = 1.0000 (bounded)")

print("\n"+"="*70)
print("Final grids across lanes: same occupied CELL set, different gid->slot assignment")
print("="*70)
def occ_cells(lane):
    g=lane['final_grid_col_major']; return frozenset((i//20,i%20) for i,v in enumerate(g) if isinstance(v,int) and v>0)
def assign(lane):
    g=lane['final_grid_col_major']; return {(i//20,i%20):v for i,v in enumerate(g) if isinstance(v,int) and v>0}
sc=occ_cells(lanes['seq']); nc=occ_cells(lanes['near']); scc=occ_cells(lanes['score'])
print(f"  occupied-cell set identical across lanes: {sc==nc==scc}  (|cells|={len(sc)})")
aseq,anear,ascore=assign(lanes['seq']),assign(lanes['near']),assign(lanes['score'])
same_seq_score=sum(1 for k in aseq if aseq[k]==ascore.get(k))
print(f"  cells where seq gid == score gid: {same_seq_score}/{len(sc)} ({100*same_seq_score/len(sc):.1f}%)")
