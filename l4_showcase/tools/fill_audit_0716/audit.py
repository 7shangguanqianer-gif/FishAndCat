# -*- coding: utf-8 -*-
import re, json, statistics, collections, sys
sys.stdout.reconfigure(encoding="utf-8")

data = open(r'F:\abb_wh_work\l4_showcase\src\s3_fill_store.js', encoding='utf-8').read()
p = json.loads(re.search(r'/\*__S3_FILL_PAYLOAD_BEGIN__\*/(.*?)/\*__S3_FILL_PAYLOAD_END__\*/', data, re.S).group(1))

de = {l['algorithm']: l for l in p['decision_evidence']['lanes']}
lanes = {l['algorithm']['id']: l for l in p['online_lanes']}

print("="*70)
print("A. TIE-DOMINANCE STATS (checklist 1)  [decision_evidence top3]")
print("="*70)
for alg in ('seq','near','score'):
    evs = de[alg]['events']
    n = len(evs)
    top1_eq_top2 = 0
    top3_all_eq = 0
    tie_sizes_sel = []       # tie_size of the selected (rank1) candidate
    legal_ge2 = 0
    for e in evs:
        t3 = e['top3']
        # objective_value present on all
        if len(t3) >= 2 and e['legal_count'] >= 2:
            legal_ge2 += 1
            if abs(t3[0]['objective_value'] - t3[1]['objective_value']) < 1e-9:
                top1_eq_top2 += 1
        if len(t3) >= 3 and e['legal_count'] >= 3:
            if (abs(t3[0]['objective_value']-t3[1]['objective_value'])<1e-9 and
                abs(t3[0]['objective_value']-t3[2]['objective_value'])<1e-9):
                top3_all_eq += 1
        sel = [c for c in t3 if c.get('selected')]
        if sel:
            tie_sizes_sel.append(sel[0]['tie_size'])
    print(f"\n-- lane {alg}: {n} events")
    print(f"   events with >=2 legal: {legal_ge2}")
    print(f"   top1==top2 objective: {top1_eq_top2}  ({100*top1_eq_top2/n:.1f}% of all events)")
    print(f"   top1==top2==top3 objective: {top3_all_eq}  ({100*top3_all_eq/n:.1f}% of all events)")
    if tie_sizes_sel:
        c = collections.Counter(tie_sizes_sel)
        print(f"   selected tie_size: min={min(tie_sizes_sel)} max={max(tie_sizes_sel)} mean={statistics.mean(tie_sizes_sel):.2f} median={statistics.median(tie_sizes_sel)}")
        print(f"   selected tie_size==1 (unique winner): {c[1]} ({100*c[1]/n:.1f}%)")
        print(f"   selected tie_size>=2 (winner tied, broke by lexicographic): {sum(v for k,v in c.items() if k>=2)} ({100*sum(v for k,v in c.items() if k>=2)/n:.1f}%)")

print("\n"+"="*70)
print("B. SCORE FOUR-TERM CONTRIBUTION (checklist 2)  [score lane top1 selected]")
print("="*70)
score_evs = de['score']['events']
terms = {'efficiency_weighted':[], 'stability_weighted':[], 'energy_proxy_weighted':[], 'position_reservation_weighted':[]}
raws  = {'f_norm':[], 'w_norm':[], 't_norm':[]}
dom_counter = collections.Counter()
loadheight_dom = 0
score_totals = []
for e in score_evs:
    sel = [c for c in e['top3'] if c.get('selected')][0]
    st = sel['score_terms']
    for k in terms: terms[k].append(st[k])
    for k in raws: raws[k].append(st[k])
    score_totals.append(st['score_total'])
    # dominant single weighted term
    wk = {k: st[k] for k in terms}
    dom = max(wk, key=wk.get)
    dom_counter[dom]+=1
    # combined load-height (stab+energy, collinear) vs reservation vs efficiency
    lh = st['stability_weighted']+st['energy_proxy_weighted']
    comps = {'load_height(stab+energy)':lh, 'reservation':st['position_reservation_weighted'], 'efficiency':st['efficiency_weighted']}
    if max(comps,key=comps.get)=='load_height(stab+energy)': loadheight_dom+=1
n=len(score_evs)
print(f"\nscore lane events: {n}")
print("weighted term  |   mean      max      min   | share of score_total(mean)")
mean_total = statistics.mean(score_totals)
for k in terms:
    v=terms[k]
    print(f"  {k:32s} mean={statistics.mean(v):.5f} max={max(v):.5f} min={min(v):.5f}  share={100*statistics.mean(v)/mean_total:.1f}%")
print(f"\n  score_total: mean={mean_total:.5f} max={max(score_totals):.5f} min={min(score_totals):.5f}")
print(f"\n  dominant single weighted term (per event): {dict(dom_counter)}")
print(f"  events where load_height(stab+energy) > reservation & efficiency: {loadheight_dom} ({100*loadheight_dom/n:.1f}%)")
print("\n  raw normalized ranges (selected slots):")
for k in raws:
    v=raws[k]
    print(f"    {k}: min={min(v):.5f} max={max(v):.5f} mean={statistics.mean(v):.5f} span={max(v)-min(v):.5f}")

print("\n"+"="*70)
print("C. TERMINAL KPI DISTINGUISHABILITY (checklist 3)")
print("="*70)
mk = {alg: lanes[alg]['metrics'] for alg in ('seq','near','score')}
keys = ['expected_retrieval_s','hot20_retrieval_s','heavy20_mean_tier','lift_work_proxy_kgm',
        'makespan_s','round_trip_path_m','fixed_score_diagnostic_total']
print(f"{'metric':32s}{'seq':>16s}{'near':>16s}{'score':>16s}")
for k in keys:
    print(f"{k:32s}{mk['seq'][k]:>16.6f}{mk['near'][k]:>16.6f}{mk['score'][k]:>16.6f}")
print("\nSCORE relative to best-of-others (lower better for retrieval/tier/energy):")
for k in ['expected_retrieval_s','hot20_retrieval_s','heavy20_mean_tier','lift_work_proxy_kgm']:
    s=mk['score'][k]; other=min(mk['seq'][k],mk['near'][k]); worst=max(mk['seq'][k],mk['near'][k])
    print(f"  {k}: score={s:.4f} seq={mk['seq'][k]:.4f} near={mk['near'][k]:.4f} | score vs best-other {100*(s-other)/other:+.2f}% | score vs seq {100*(s-mk['seq'][k])/mk['seq'][k]:+.2f}%")
print("\nIdentical-across-lanes check:")
for k in keys:
    vals={alg:mk[alg][k] for alg in ('seq','near','score')}
    print(f"  {k}: identical={len(set(vals.values()))==1}  values={set(round(v,6) for v in vals.values())}")

print("\n"+"="*70)
print("D. CARGO CATALOG DISTRIBUTION (checklist 4)  267 goods")
print("="*70)
cat = p['cargo_catalog']
print("count:", len(cat))
for field in ('freq','weight_kg','volume_m3'):
    vals=[g[field] for g in cat]
    print(f"\n {field}: min={min(vals):.3f} max={max(vals):.3f} mean={statistics.mean(vals):.3f} median={statistics.median(vals):.3f} stdev={statistics.pstdev(vals):.3f}")
    # histogram
    lo,hi=min(vals),max(vals); nb=10; w=(hi-lo)/nb if hi>lo else 1
    h=collections.Counter(min(nb-1,int((v-lo)/w)) for v in vals)
    for b in range(nb):
        print(f"   [{lo+b*w:7.2f},{lo+(b+1)*w:7.2f}) {h[b]:4d} {'#'*h[b]}")
grades=collections.Counter(g['grade'] for g in cat)
print("\n grade:", dict(grades))
freqs=[g['freq'] for g in cat]
print(f"\n freq>=3.2: {sum(1 for f in freqs if f>=3.2)}  freq>=5: {sum(1 for f in freqs if f>=5)}  freq>=10: {sum(1 for f in freqs if f>=10)}  freq<2: {sum(1 for f in freqs if f<2)}")
print(f" freq f_norm range (f/100): {min(freqs)/100:.4f}..{max(freqs)/100:.4f}")
# gid vs attribute correlation
gids=[g['gid'] for g in cat]
print(f"\n gid range: {min(gids)}..{max(gids)}  sorted&contiguous: {gids==list(range(1,268))}")
import math
def corr(a,b):
    ma,mb=statistics.mean(a),statistics.mean(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0
print(f" corr(gid, freq)={corr(gids,freqs):+.3f}  corr(gid,weight)={corr(gids,[g['weight_kg'] for g in cat]):+.3f}  corr(gid,vol)={corr(gids,[g['volume_m3'] for g in cat]):+.3f}")
inb = p['shared_input_provenance']['inbound_order']
print(f" inbound_order == gid 1..267 (arrival=catalog order): {inb==list(range(1,268))}")
