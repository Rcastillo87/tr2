import asyncio
import asyncpg
import httpx
import os
import json
from dotenv import load_dotenv

# Cargar el .env de la carpeta actual (python-engine)
load_dotenv()
DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

async def main():
    print("Conectando a la base de datos...")
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
    
    async with pool.acquire() as conn:
        configs = await conn.fetch("SELECT id, display_name, strategy_class, symbol, interval, params FROM paper_strategy_configs WHERE active = true")
    
    print(f"Encontradas {len(configs)} configuraciones activas.\\n")
    
    for c in configs:
        config_id = c['id']
        name = c['display_name']
        print(f"── Corriendo backtest para: {name} ──")
        
        params = c['params'] if isinstance(c['params'], dict) else json.loads(c['params'])
        
        strategy_name = "VWAP Tendencia"
        if c['strategy_class'] == 'VwapStrategy':
            strategy_name = "VWAP Tendencia" if params.get('mode') == 'trend_follow' else "VWAP Reversión"
        elif c['strategy_class'] == 'MeanReversionStrategy':
            strategy_name = "Reversión a la Media"
        elif c['strategy_class'] == 'EmaDonchianStrategy':
            strategy_name = "Tendencia EMA/Donchian"
            
        payload = {
            "strategy": strategy_name,
            "symbol": c['symbol'],
            "interval": c['interval'],
            "walk_forward": True,
            "n_windows": 5,
            "monthly_breakdown": True,
            **params
        }
        payload.setdefault('max_leverage', 1.0)
        
        try:
            r = httpx.post("http://localhost:8002/v1/backtest/run", headers={"X-Internal-API-Key": "trading2_internal_key_2026"}, json=payload, timeout=300)
            r.raise_for_status()
        except Exception as e:
            print(f"  ❌ Error en petición HTTP: {e}\\n")
            continue
            
        result = r.json().get('result', {})
        agg = result.get('aggregate_metrics', {})
        
        sharpe = agg.get('sharpe_ratio', 0)
        wr = agg.get('win_rate', 0)
        pf = agg.get('profit_factor', 0)
        ret = agg.get('total_return_pct', 0)
        
        print(f"  ✅ Resultados: Sharpe={sharpe}, WR={wr}%, PF={pf}, Ret={ret}%")
        
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE paper_strategy_configs 
                SET avg_win_rate = $1,
                    sharpe_ratio = $2,
                    profit_factor = $3,
                    total_return_pct = $4,
                    updated_at = now()
                WHERE id = $5
            """, wr, sharpe, pf, ret, config_id)
        print(f"  💾 DB actualizada para {name}\\n")
        
    await pool.close()
    print("✅ Proceso completo.")

if __name__ == "__main__":
    asyncio.run(main())
