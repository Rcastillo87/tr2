"""Reglas del motor V3 (datos sintéticos). Uso: cd python-engine && venv/bin/python ../tests/Forensic/engine_rules_test.py"""
import sys, numpy as np, pandas as pd
import os; sys.path.insert(0, os.getcwd())  # ejecutar desde python-engine/
from datetime import datetime, timedelta, timezone
from backtesting.engine import BacktestEngine, compute_regimes
from backtesting.strategies.base_strategy import BaseStrategy
from indicators.regime_indicators import classify_regime, calculate_atr, calculate_adx, calculate_bb_width

class Sig(BaseStrategy):
    """Señal long en índices dados."""
    idx = set()
    def generate_signals(self, df):
        df = df.copy(); df['signal'] = 0
        df.loc[df.index.isin(self.idx), 'signal'] = 1
        return df

def mk(n, t0=datetime(2026,1,1,tzinfo=timezone.utc)):
    return pd.DataFrame({'time':[t0+timedelta(hours=i) for i in range(n)],'open':100.0,'high':100.5,'low':99.5,'close':100.0,'volume':1.0})
P = dict(symbol='X', interval='60', sl_pct=1.0, tp_pct=2.0, be_pct=1.5, max_duration=5, regime_filter=False, commission_pct=0.0)
fails=0
def check(name, ok, d=''):
    global fails; fails += 0 if ok else 1; print(('PASS ' if ok else 'FAIL ')+name+('  -> '+str(d) if d else ''))

# 1. Vela de entrada cuenta: señal en vela 10, entrada open vela 11, la vela 11 toca SL (low 98.9)
df = mk(30); df.loc[11,'low']=98.9
s=Sig(P); s.idx={10}; r=BacktestEngine(s,df).run()
t=r['trades'][0]; check('SL en la vela de entrada', t['exit_reason']=='stop_loss' and t['bars_open']==1, (t['exit_reason'],t['bars_open']))

# 2. SL antes que BE en la misma vela: vela 12 toca BE (101.5) y SL (99) -> stop_loss con pérdida
df = mk(30); df.loc[12,'high']=101.6; df.loc[12,'low']=98.9
s=Sig(P); s.idx={10}; t=BacktestEngine(s,df).run()['trades'][0]
check('SL vigente antes que break-even', t['exit_reason']=='stop_loss' and t['pnl']<0, (t['exit_reason'],t['pnl']))

# 3. SL antes que TP en la misma vela
df = mk(30); df.loc[12,'high']=102.5; df.loc[12,'low']=98.9
s=Sig(P); s.idx={10}; t=BacktestEngine(s,df).run()['trades'][0]
check('SL antes que TP en la misma vela', t['exit_reason']=='stop_loss', t['exit_reason'])

# 4. Duración: exactamente max_duration velas
df = mk(30); s=Sig(P); s.idx={10}; t=BacktestEngine(s,df).run()['trades'][0]
check('time_exit tras exactamente 5 velas', t['exit_reason']=='time_exit' and t['bars_open']==5, (t['exit_reason'],t['bars_open']))

# 5. Slippage + comisión
P2=dict(P, commission_pct=0.055); s=Sig(P2); s.idx={10}; s.slippage_pct=0.05
t=BacktestEngine(s,mk(30)).run()['trades'][0]
check('entrada con slippage en contra', abs(t['entry_price']-100*1.0005)<1e-9, t['entry_price'])
check('salida con slippage en contra', abs(t['exit_price']-100*0.9995)<1e-9, t['exit_price'])
check('comisión entrada+salida', abs(t['commission']-(t['entry_price']+t['exit_price'])*t['size']*0.00055)<1e-3, t['commission'])

# 6. Calentamiento: señales antes de trade_from no operan
df=mk(60); s=Sig(P); s.idx={5,40}; r=BacktestEngine(s,df,trade_from=df['time'][30]).run()
check('sin operaciones antes de trade_from', len(r['trades'])==1 and r['trades'][0]['entry_time']==df['time'][41], [str(x['entry_time']) for x in r['trades']])

# 7. Régimen vectorizado == classify_regime fila a fila (datos aleatorios)
rng=np.random.default_rng(1); c=100+np.cumsum(rng.normal(0,1,600))
d=pd.DataFrame({'time':pd.date_range('2026-01-01',periods=600,freq='h',tz='UTC'),'open':c,'high':c+rng.random(600)*2,'low':c-rng.random(600)*2,'close':c+rng.normal(0,.3,600),'volume':1.0})
vec=compute_regimes(d,25,20,'RANGING')
atr=calculate_atr(d); adx=calculate_adx(d); bb=calculate_bb_width(d); aa=atr.rolling(50).mean(); ba=bb.rolling(50).mean()
row=[classify_regime(adx[i],atr[i],aa[i],bb[i],ba[i],25,20,'RANGING') for i in range(600)]
check('régimen vectorizado idéntico a classify_regime', list(vec)==row, sum(a!=b for a,b in zip(vec,row)))

# 8. Régimen de la vela de SEÑAL (cerrada), no de la de entrada
class OnlyRanging(Sig): pass
P3=dict(P, regime_filter=True); s=OnlyRanging(P3); s.allowed_regimes=['RANGING']; s.idx={10}
e=BacktestEngine(s,mk(30),regime_data={str(t):'TRENDING' for t in mk(30)['time']}); e.regime_data[str(mk(30)['time'][10])]='RANGING'
r=e.run(); check('usa régimen de la vela de señal (10=RANGING, 11=TRENDING)', len(r['trades'])==1, len(r['trades']))

# 9. Velas de 1m: la sub-vela decide el orden real (TP antes que SL en el tiempo)
df=mk(30); df.loc[12,'high']=102.5; df.loc[12,'low']=98.9
m_t=[df['time'][12]+timedelta(minutes=k) for k in range(60)]
mh=[100.4]*60; ml=[99.6]*60; mh[10]=102.2; ml[40]=98.8   # TP en minuto 10, SL en minuto 40
mdf=pd.DataFrame({'time':m_t,'open':100.0,'high':mh,'low':ml,'close':100.0,'volume':1.0})
# minutos para velas 11..13 sin eventos
for v in (11,13):
    mdf=pd.concat([mdf,pd.DataFrame({'time':[df['time'][v]+timedelta(minutes=k) for k in range(60)],'open':100.0,'high':100.4,'low':99.6,'close':100.0,'volume':1.0})])
s=Sig(P); s.idx={10}; t=BacktestEngine(s,df,minute_df=mdf.sort_values('time')).run()['trades'][0]
check('1m: TP alcanzado antes que el SL en el tiempo', t['exit_reason']=='take_profit_1', t['exit_reason'])
print('\nRESULTADO:', 'TODO OK' if fails==0 else f'{fails} FALLO(S)')
