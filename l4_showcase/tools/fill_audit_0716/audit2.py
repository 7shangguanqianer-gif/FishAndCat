# -*- coding: utf-8 -*-
import re, json, collections, statistics, sys, math
sys.path.insert(0, r'F:\abb_wh_work\sim')
sys.stdout.reconfigure(encoding="utf-8")
import warehouse_sim as ws

data = open(r'F:\abb_wh_work\l4_showcase\src\s3_fill_store.js', encoding='utf-8').read()
p = json.loads(re.search(r'/\*__S3_FILL_PAYLOAD_BEGIN__\*/(.*?)/\*__S3_FILL_PAYLOAD_END__\*/', data, re.S).group(1))
de = {l['algorithm']: l for l in p['decision_evidence']['lanes']}
lanes = {l['algorithm']['id']: l for l in p['online_lanes']}

print("="*70)
print("F. TRAVEL_TIME ISO-ZONE STRUCTURE (checklist 6)  ACCEL=True (fill uses accel)")
print("="*70)
ws.ACCEL = True
tmax = ws.t_max_now()
print(f"t_max_now (accel) = {tmax:.6f}  [normalizer]")
# build travel_time over 20x20 managed (non-preoccupied) slots
tt = {}
for c in range(20):
    for t in range(20):
        tt[(c,t)] = round(ws.travel_time(c,t),9)
# distinct travel values and multiplicities over ALL 400 slots
vals = collections.Counter(tt.values())
print(f"distinct travel_time values over 400 slots: {len(vals)}")
sizes = sorted(vals.values(), reverse=True)
print(f"iso-time group sizes (top): {sizes[:15]}")
print(f"max iso group size: {max(vals.values())}  (# slots sharing one travel value)")
# how many slots have col-independent travel (vertical dominates)? for tier>=?, all cols equal
col_indep_tiers=[]
for t in range(20):
    row = set(tt[(c,t)] for c in range(20))
    if len(row)==1:
        col_indep_tiers.append(t)
print(f"tiers where ALL 20 cols share one travel_time (vertical dominates): {col_indep_tiers}")
print(f"  -> {len(col_indep_tiers)} tiers x 20 cols = {len(col_indep_tiers)*20} slots have travel independent of column")

print("\n"+"="*70)
print("A2. travel_time_s top3-equality cross-check (brief claim SEQ6/NEAR73/SCORE67)")
print("="*70)
for alg in ('seq','near','score'):
    evs=de[alg]['events']; n=len(evs); eq3=0; eq2=0
    for e in evs:
        t3=e['top3']
        tts=[c['travel_time_s'] for c in t3]
        if len(tts)>=3 and abs(tts[0]-tts[1])<1e-9 and abs(tts[0]-tts[2])<1e-9: eq3+=1
        if len(tts)>=2 and abs(tts[0]-tts[1])<1e-9: eq2+=1
    print(f"  {alg}: top3 travel_time all equal = {eq3} ({100*eq3/n:.1f}%) ; top2 equal = {eq2} ({100*eq2/n:.1f}%)")

print("\n"+"="*70)
print("G. FINAL-GRID PLACEMENT PATTERN (frontend 'far-column backfill' / identical rows)")
print("="*70)
# final_grid_col_major: index = col*TIERS+tier, value: -1 pre, 0 empty, gid occupied
def grid_from(lane):
    g=lane['final_grid_col_major']
    occ={}
    for c in range(20):
        for t in range(20):
            v=g[c*20+t]
            occ[(c,t)]=v
    return occ
# characterize per-tier which columns filled, and the order via events (event_index vs slot)
for alg in ('seq','score','near'):
    lane=lanes[alg]
    # map slot -> event_index (fill order)
    order={}
    for e in lane['events']:
        c,t=e['decision']['selected_slot']
        order[(c,t)]=e['event_index']
    # For a few representative tiers, list the fill order of columns
    print(f"\n-- {alg}: within-tier column fill order (event_index by column), sample tiers")
    for t in [0,2,7,12,19]:
        cols_at_t=sorted([(c,order.get((c,t))) for c in range(20) if (c,t) in order and order.get((c,t))], key=lambda x:x[1])
        seq_cols=[c for c,_ in cols_at_t]
        print(f"   tier {t:2d}: fill col sequence = {seq_cols}")

print("\n"+"="*70)
print("H. INTEGRITY SPOTCHECK (checklist 8)  bundle + 5 events per lane")
print("="*70)
import hashlib
def canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(v): return hashlib.sha256(canon(v)).hexdigest()
# bundle_payload_sha256: recompute over payload minus that key
body={k:v for k,v in p.items() if k!='bundle_payload_sha256'}
calc=sha(body)
print(f"bundle_payload_sha256 stored : {p['bundle_payload_sha256']}")
print(f"bundle_payload_sha256 recalc : {calc}")
print(f"  MATCH: {calc==p['bundle_payload_sha256']}")
# event chain spotcheck: recompute event_sha256 for 5 events in score lane
for alg in ('seq','near','score'):
    lane=lanes[alg]; evs=lane['events']; ok=0; checked=0
    idxs=[0,66,133,200,266]
    for i in idxs:
        e=evs[i]; checked+=1
        rec={k:v for k,v in e.items() if k!='event_sha256'}
        if sha(rec)==e.get('event_sha256'): ok+=1
    # inventory chain: after[i] should equal before[i+1]
    chain_ok=all(evs[i]['inventory_after_sha256']==evs[i+1]['inventory_before_sha256'] for i in range(len(evs)-1))
    print(f"  {alg}: event_sha256 recompute {ok}/{checked} match ; inventory before/after chain contiguous={chain_ok}")

print("\n"+"="*70)
print("I. BOUNDARY / PREOCCUPIED (checklist 9)")
print("="*70)
pre=sum(1 for c in range(20) for t in range(20) if ws.preoccupied(c,t,'sum'))
print(f"preoccupied (col+tier)%3==0 count: {pre}  (expect 133)")
print(f"managed capacity: {400-pre}  (expect 267)")
cap=p['capacity']
print(f"payload capacity: total={cap['total_slots']} pre={cap['preoccupied_slots']} managed={cap['managed_capacity']}")
# tier caps: does any good exceed any tier cap? top tier cap:
print(f"tier_cap(0)={ws.tier_cap(0)}  tier_cap(19)={ws.tier_cap(19)}  (max good weight=60)")
cat=p['cargo_catalog']
maxw=max(g['weight_kg'] for g in cat)
print(f"max good weight={maxw}; goods exceeding tier19 cap({ws.tier_cap(19)}): {sum(1 for g in cat if g['weight_kg']>ws.tier_cap(19))}")
print(f"  -> every good fits EVERY tier by weight: {all(g['weight_kg']<=ws.tier_cap(19) for g in cat)}")
# volume: CELL_VOL=1.0, max vol 0.9
print(f"max good vol={max(g['volume_m3'] for g in cat)}; CELL_VOL={ws.CELL_VOL}; goods exceeding: {sum(1 for g in cat if g['volume_m3']>ws.CELL_VOL)}")
