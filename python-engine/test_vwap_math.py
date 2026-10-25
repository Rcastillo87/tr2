import asyncio
import pandas as pd
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('.env')
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def test_btc():
    pool = await asyncpg.create_pool(DB_DSN)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT time, open, high, low, close, volume FROM ohlcv_data WHERE symbol = 'BTCUSDT' AND interval = '240' ORDER BY time ASC LIMIT 500")
        df = pd.DataFrame([dict(r) for r in rows])
        
    if len(df) == 0:
        print('❌ ERROR: No hay datos de BTCUSDT en la DB.')
        return

    # EL FIX: Convertimos las columnas numéricas de Decimal a float
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    print(f'✅ Datos cargados: {len(df)} velas de BTCUSDT.')
    
    code = '''
import pandas as pd
class VwapStrategy:
    name = "VWAP"
    allowed_regimes = ["TRENDING", "RANGING", "VOLATILE"]
    def __init__(self, params: dict):
        self.mode = params.get('mode', 'reversion')
        self.vwap_std_entry = params.get('vwap_std_entry', 1.0)
        self.zone_bars = params.get('zone_bars', 4)
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
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
    strat = StratClass({'vwap_std_entry': 1.0, 'zone_bars': 4})
    
    df = strat.prepare(df)
    
    print('\n--- ESTADÍSTICAS DE VWAP Y DESVIACIÓN ---')
    print('VWAP Std Dev Min:', df['vwap_std_dev'].min())
    print('VWAP Std Dev Max:', df['vwap_std_dev'].max())

    df = strat.generate_signals(df)
    signals = df[df['signal'] != 0]
    print(f'\n✅ Señales generadas para BTCUSDT: {len(signals)}')
    
    if len(signals) > 0:
        print("\nPrimeras 5 señales:")
        print(signals[['time', 'close', 'vwap', 'vwap_upper_entry', 'vwap_lower_entry', 'signal']].head(5))
    else:
        print("\n--- DIAGNÓSTICO DE POR QUÉ NO HAY SEÑALES ---")
        crosses = df[(df['close'] > df['vwap_upper_entry']) | (df['close'] < df['vwap_lower_entry'])]
        print(f"Velas donde el precio rompió las bandas: {len(crosses)}")
        if len(crosses) > 0:
            print("¡El precio rompió las bandas, pero la lógica de 'zone_bars' o el filtro lo bloqueó!")
        else:
            print("El precio NUNCA logró romper las bandas. La desviación estándar está muy ancha.")

asyncio.run(test_btc())
