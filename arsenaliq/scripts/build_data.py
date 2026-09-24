#!/usr/bin/env python3
"""ArsenalIQ data builder.
Fetches public Baseball Savant leaderboards, merges by MLBAM player id, and writes data/pitchers.json.
Run: python scripts/build_data.py --year 2026 --min-pitches 50
"""
from __future__ import annotations
import argparse, io, json, math, statistics, urllib.parse, urllib.request
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
PITCH_NAMES={'FF':'Four-Seam','SI':'Sinker','FC':'Cutter','SL':'Slider','ST':'Sweeper','SV':'Slurve','CU':'Curveball','KC':'Knuckle Curve','CH':'Changeup','FS':'Splitter','KN':'Knuckleball'}

def get_csv(path, params):
    url='https://baseballsavant.mlb.com/leaderboard/'+path+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 ArsenalIQ research project'})
    with urllib.request.urlopen(req,timeout=90) as r: raw=r.read().decode('utf-8-sig')
    return pd.read_csv(io.StringIO(raw), low_memory=False)

def num(v):
    try:
        if pd.isna(v): return None
        return float(v)
    except: return None

def pct_rank(vals,v,higher=True):
    vals=[x for x in vals if x is not None and math.isfinite(x)]
    if v is None or not vals:return 50
    p=sum(x<=v for x in vals)/len(vals)
    if not higher:p=1-p
    return p

def grade_from_pct(p):
    # smooth scouting scale; 50 average, 80/20 tails
    return int(max(20,min(80,round((50+(p-.5)*60)/5)*5)))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--year',type=int,default=2026); ap.add_argument('--min-pitches',type=int,default=50); a=ap.parse_args(); y=a.year
    print('Fetching Baseball Savant leaderboards…')
    arsenal=get_csv('pitch-arsenal-stats',{'type':'pitcher','pitchType':'','year':y,'team':'','min':1,'csv':'true'})
    velo=get_csv('pitch-arsenals',{'year':y,'min':a.min_pitches,'type':'avg_speed','hand':'','csv':'true'})
    movement=get_csv('pitch-movement',{'year':y,'team':'','min':a.min_pitches,'pitch_type':'ALL','hand':'','x':'pitcher_break_x_hidden','z':'pitcher_break_z_hidden','csv':'true'})
    xstats=get_csv('expected_statistics',{'type':'pitcher','year':y,'position':'','team':'','filterType':'pa','min':1,'csv':'true'})
    arm=get_csv('pitcher-arm-angles',{'year':y,'csv':'true'})
    # Universe = union of all ids; velo min-pitch threshold is primary inclusion gate when available.
    ids=set()
    for df,col in [(velo,'pitcher'),(arsenal,'player_id'),(movement,'pitcher_id'),(xstats,'player_id'),(arm,'pitcher')]:
        if col in df: ids |= set(pd.to_numeric(df[col],errors='coerce').dropna().astype(int))
    # Distributions by pitch type for outcome grading.
    dist={}
    for pt,g in arsenal.groupby('pitch_type'):
        dist[pt]={k:[num(x) for x in g[c]] if c in g else [] for k,c in {'whiff':'whiff_percent','rv':'run_value_per_100','xwoba':'est_woba','hard':'hard_hit_percent'}.items()}
    # velo lookup
    vmap={}
    if 'pitcher' in velo:
        for _,r in velo.iterrows():
            pid=int(r['pitcher']); vmap[pid]={pt:num(r.get(pt.lower()+'_avg_speed')) for pt in PITCH_NAMES}
    # movement lookup
    mmap={}
    if 'pitcher_id' in movement:
        for _,r in movement.iterrows():
            try: pid=int(r['pitcher_id'])
            except: continue
            pt=str(r.get('pitch_type',''))
            mmap[(pid,pt)]={k:num(r.get(c)) for k,c in {'ivb':'pitcher_break_z_induced','hb':'pitcher_break_x','diff_z':'diff_z','diff_x':'diff_x','move_velo':'avg_speed','pitches':'pitches_thrown'}.items()}
    # xstats lookup
    xs={}
    if 'player_id' in xstats:
        for _,r in xstats.iterrows():
            try: xs[int(r['player_id'])]=r
            except: pass
    arms={}
    if 'pitcher' in arm:
        for _,r in arm.iterrows():
            try: arms[int(r['pitcher'])]=r
            except: pass
    players=[]
    for pid in sorted(ids):
        ag=arsenal[pd.to_numeric(arsenal.get('player_id'),errors='coerce')==pid] if 'player_id' in arsenal else pd.DataFrame()
        name=None; team='—'
        for df,col,nc in [(ag,'player_id','last_name, first_name'),(velo,'pitcher','last_name, first_name'),(movement,'pitcher_id','last_name, first_name'),(xstats,'player_id','last_name, first_name')]:
            if col in df:
                z=df[pd.to_numeric(df[col],errors='coerce')==pid]
                if len(z):
                    name=str(z.iloc[0].get(nc,name or pid)); team=str(z.iloc[0].get('team_name_alt',z.iloc[0].get('team_name_abbrev',team))); break
        if not name: continue
        if ',' in name:
            last,first=[s.strip() for s in name.split(',',1)]; name=f'{first} {last}'
        pitches=[]
        for _,r in ag.iterrows():
            pt=str(r.get('pitch_type','')); d=dist.get(pt,{})
            wh=num(r.get('whiff_percent')); rv=num(r.get('run_value_per_100')); xw=num(r.get('est_woba')); hh=num(r.get('hard_hit_percent')); usage=num(r.get('pitch_usage')); n=num(r.get('pitches'))
            components=[pct_rank(d.get('whiff',[]),wh,True),pct_rank(d.get('rv',[]),rv,False),pct_rank(d.get('xwoba',[]),xw,False),pct_rank(d.get('hard',[]),hh,False)]
            p=sum(components)/len(components); g=grade_from_pct(p)
            mv=mmap.get((pid,pt),{}); vel=(vmap.get(pid,{}) or {}).get(pt) or mv.get('move_velo')
            pitches.append({'code':pt,'name':str(r.get('pitch_name') or PITCH_NAMES.get(pt,pt)),'usage':usage,'pitches':n,'velo':vel,'whiff':wh,'rv100':rv,'xwoba':xw,'hardhit':hh,'ivb':mv.get('ivb'),'hb':mv.get('hb'),'diff_z':mv.get('diff_z'),'diff_x':mv.get('diff_x'),'grade':g})
        if not pitches:
            # keep pitcher universe even if no arsenal row qualifies
            for pt,v in (vmap.get(pid,{}) or {}).items():
                if v is not None:pitches.append({'code':pt,'name':PITCH_NAMES.get(pt,pt),'usage':None,'pitches':None,'velo':v,'grade':50})
        weights=[(p.get('usage') or p.get('pitches') or 1) for p in pitches]
        ars=round(sum(p['grade']*w for p,w in zip(pitches,weights))/sum(weights)/5)*5 if pitches else 50
        xr=xs.get(pid); era=num(xr.get('era')) if xr is not None else None; xera=num(xr.get('xera')) if xr is not None else None
        ar=arms.get(pid); hand=str(ar.get('pitch_hand','—')) if ar is not None else '—'; angle=num(ar.get('ball_angle')) if ar is not None else None; relz=num(ar.get('release_ball_z')) if ar is not None else None
        # Transparent projection: arsenal + xERA signal; command stays ungraded until pitch-level location model is run.
        perf=50 if xera is None else grade_from_pct(max(0,min(1,(6.5-xera)/5.5)))
        proj=round((.7*ars+.3*perf)/5)*5
        gap=int(proj-perf); flag='Breakout' if gap>=8 else ('Regression' if gap<=-8 else 'Stable')
        strengths=[]; weaknesses=[]
        for p in sorted(pitches,key=lambda z:z.get('grade',50),reverse=True)[:2]:
            if p.get('grade',50)>=60: strengths.append(f"{p['name']} grades as an above-average weapon ({p['grade']})")
        for p in sorted(pitches,key=lambda z:z.get('grade',50))[:2]:
            if p.get('grade',50)<=45: weaknesses.append(f"{p['name']} currently grades below average ({p['grade']})")
        if not strengths: strengths=['No pitch currently clears the 60-grade threshold in the available public sample.']
        if not weaknesses: weaknesses=['No major pitch-quality weakness flagged; location and role context still require review.']
        players.append({'id':pid,'name':name,'team':team,'role':'P','hand':hand,'era':era,'xera':xera,'ars':ars,'cmd':None,'proj':int(proj),'gap':gap,'flag':flag,'armAngle':angle,'releaseHeight':relz,'pitches':pitches,'strength':strengths,'weak':weaknesses,'source':'Baseball Savant','year':y})
    out={'meta':{'year':y,'min_pitches':a.min_pitches,'count':len(players),'generated_by':'ArsenalIQ build_data.py','note':'Public Baseball Savant leaderboards; model grades are ArsenalIQ calculations, not MLB/FanGraphs grades.'},'pitchers':players}
    (DATA/'pitchers.json').write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
    print(f"Wrote {len(players)} pitchers to {DATA/'pitchers.json'}")

if __name__=='__main__': main()
