import asyncio
import pandas as pd
import asyncpg
import os
from dotenv import load_dotenv
from backtesting.engine import BacktestEngine
from backtesting.strategies.base_strategy import BaseStrategy

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test_btc():
    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT time, open, high, low, close, volume FROM ohlcv_data WHERE symbol = 'BTCUSDT' AND interval = '240' ORDER BY time ASC LIMIT 1000")
        df = pd.DataFrame([dict(r) for r in rows])

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    code = '''
import pandas as pd
from backtesting.strategies.base_strategy import BaseStrategy
class VwapStrategy(BaseStrategy):
    name = "VWAP"
    allowed_regimes = ["TRENDING", "RANGING", "VOLATILE"]
    def __init__(self, params: dict):
        super().__init__(params)
        self.mode = params.get('mode', 'reversion')
        self.vwap_std_entry = params.get('vwap_std_entry', 1.0)
        self.zone_bars = params.get('zone_bars', 4)
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        df['typical'] = (df['high'] + df['low'] + df['close']) / 3
        typical_arr = df['typical'].values
        volume_arr = df['volume'].values
        vwap_list = []
        std_list = []
        window = 20
        for i in range(len(df)):
            start = max(0, i - window + 1)
            t = typical_arr[start:i+1]
            v = volume_arr[start:i+1]
            vol_sum = v.sum()
            if vol_sum > 0:
                vwap_val = (t * v).sum() / vol_sum
                sq_diff = ((t - vwap_val) ** 2) * v
                std_val = (sq_diff.sum() / vol_sum) ** 0.5
            else:
                vwap_val = typical_arr[i]
                std_val = 0.0
            vwap_list.append(vwap_val)
            std_list.append(std_val)
        df['vwap'] = vwap_list
        df['vwap_std_dev'] = std_list
        df['vwap_upper_entry'] = df['vwap'] + (self.vwap_std_entry * df['vwap_std_dev'])
        df['vwap_lower_entry'] = df['vwap'] - (self.vwap_std_entry * df['vwap_std_dev'])
        return df
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0
        last_zone_bar = {'LONG': -10_000, 'SHORT': -10_000}
        for i in range(20, len(df)):
            row = df.iloc[i]
            if pd.isna(row['vwap_std_dev']) or row['vwap_std_dev'] == 0:
                continue
            price = row['close']
            upper = row['vwap_upper_entry']
            lower = row['vwap_lower_entry']
            direction = None
            if price > upper: direction = 'SHORT'
            elif price < lower: direction = 'LONG'
            if direction is None: continue
            zone_id = i // self.zone_bars
            last_zone_id = last_zone_bar[direction] // self.zone_bars
            if zone_id == last_zone_id: continue
            last_zone_bar[direction] = i
            df.at[df.index[i], 'signal'] = 1 if direction == 'LONG' else -1
        return df
'''

    namespace = {}
    exec(code, namespace)
    StratClass = namespace['VwapStrategy']
    
    # Inyectamos SL y TP dentro de la estrategia
    strat = StratClass({
        'vwap_std_entry': 1.0, 
        'zone_bars': 4,
        'sl_pct': 1.0, 
        'tp_pct': 1.5, 
        'be_pct': 2.0, 
        'max_duration': 24
    })

    print("Ejecutando BacktestEngine con las mismas condiciones de la web...")
    
    # 1. Constructor correcto (sin symbol, sl_pct, etc)
    engine = BacktestEngine(
        strategy=strat, 
        df=df, 
        initial_balance=10000.0,
        risk_per_trade_pct=1.0
    )
    
    # 2. Ejecutamos el método principal
    if hasattr(engine, 'run'):
        results = engine.run()
    else:
        print("Métodos disponibles:", dir(engine))
        return

    # 3. Extraemos los trades
    trades = results.get('trades', [])
    print(f"\n✅ Trades ejecutados por el motor: {len(trades)}")
    
    if len(trades) == 0:
        print("❌ El motor no ejecutó ningún trade, incluso teniendo 101 señales en crudo.")
        print("Esto significa que el motor tiene una condición de entrada que está rechazando.")
        # Intentamos ver el regimen
        if hasattr(engine, 'get_current_regime'):
             regime = engine.get_current_regime(df, trending_threshold=25, ranging_threshold=20, ambiguous_as='RANGING')
             print(f"Régimen detectado por el motor: {regime}")
    else:
        print("Los trades se abrieron correctamente en el motor. El problema está en la interfaz (UI) o en cómo se envían los datos desde Laravel.")

asyncio.run(test_btc())
