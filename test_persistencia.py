import subprocess
import re
import os
import base64

print("⏳ 1. Creando backtest con valores extremos...")

php_create = r"""
$bt = new \App\Models\Backtest();
$bt->strategy_id = 5; // VWAP Reversión
$bt->symbols = ['BTCUSDT'];
$bt->interval = '240'; // H4
$bt->months = 3;
$bt->config_params = [
    'sl_pct' => 2.5,
    'tp_pct' => 5.0,
    'risk_per_trade_pct' => 2.0,
    'commission_pct' => 0.1,
    'be_pct' => 1.5,
    'max_duration' => 48,
    'regime_adx_trending' => 35,
    'regime_adx_ranging' => 15,
    'regime_ambiguous_as' => 'TRENDING',
    'volume_filter_period' => 50,
    'volume_filter_mult' => 2.5,
    'trailing_mode' => 'atr',
    'trailing_atr_mult' => 3.5,
    'trailing_distance_pct' => 2.0,
    'trailing_activation_buffer_pct' => 1.5,
    'volume_filter' => true,
    'macro_trend_filter' => true,
    'regime_filter' => true,
    'max_duration_profit' => true,
    'close_on_opposite' => true
];
$bt->metrics = [];
$bt->hash = 'test_persist_' . time();
$bt->save();
echo $bt->id;
"""

# Escribir el archivo PHP y ejecutarlo
with open('/tmp/create_bt.php', 'w') as f:
    f.write(php_create)

res = subprocess.run(["php", "artisan", "tinker", "/tmp/create_bt.php"], capture_output=True, text=True)
bt_id = res.stdout.strip().split('\n')[-1].strip()

if not bt_id.isdigit():
    print(f"❌ Error creando backtest: {res.stderr}")
    exit()

print(f"✅ Backtest creado con ID: {bt_id}")
print("⏳ 2. Renderizando vista...")

php_render = f"""
$bt = \\App\\Models\\Backtest::find({bt_id});
$strategy = \\App\\Models\\Strategy::find($bt->strategy_id);
$html = view('backtesting.run', [
    'strategies' => collect(),
    'symbols' => [],
    'intervals' => [],
    'symbolBrokerMap' => [],
    'paperConfigsForPreload' => collect(),
    'result' => null,
    'implementParams' => [],
    'error' => null,
    'backtestToLoad' => $bt,
    'selectedSymbols' => $bt->symbols,
    'strategyToLoad' => $strategy,
])->render();
echo base64_encode($html);
"""

with open('/tmp/render_bt.php', 'w') as f:
    f.write(php_render)

res = subprocess.run(["php", "artisan", "tinker", "/tmp/render_bt.php"], capture_output=True, text=True)

try:
    html_b64 = res.stdout.strip().split('\n')[-1].strip()
    html = base64.b64decode(html_b64).decode('utf-8')
except Exception as e:
    print(f"❌ Error renderizando: {res.stderr}")
    subprocess.run(["php", "artisan", "tinker", "--execute", f"\\App\\Models\\Backtest::find({bt_id})->delete();"])
    exit()

print("🔬 3. Verificando valores...")
print("-" * 70)

checks = [
    ("SL = 2.5%", r'name="sl_pct"[^>]*value="2\.5"'),
    ("TP = 5.0%", r'name="tp_pct"[^>]*value="5\.0"'),
    ("Riesgo = 2.0%", r'name="risk_per_trade_pct"[^>]*value="2\.0"'),
    ("Comisión = 0.1%", r'name="commission_pct"[^>]*value="0\.1"'),
    ("BE = 1.5%", r'name="be_pct"[^>]*value="1\.5"'),
    ("Duración = 48", r'name="max_duration"[^>]*value="48"'),
    ("ADX Trending = 35", r'name="regime_adx_trending"[^>]*value="35"'),
    ("ADX Ranging = 15", r'name="regime_adx_ranging"[^>]*value="15"'),
    ("Caso Ambiguo = TRENDING", r'<option value="TRENDING"[^>]*selected'),
    ("Volumen Período = 50", r'name="volume_filter_period"[^>]*value="50"'),
    ("Volumen Mult = 2.5", r'name="volume_filter_mult"[^>]*value="2\.5"'),
    ("Trailing Mode = atr", r'<option value="atr"[^>]*selected'),
    ("Trailing ATR Mult = 3.5", r'name="trailing_atr_mult"[^>]*value="3\.5"'),
    ("Trailing Dist = 2.0", r'name="trailing_distance_pct"[^>]*value="2\.0"'),
    ("Trailing Buffer = 1.5", r'name="trailing_activation_buffer_pct"[^>]*value="1\.5"'),
    ("Checkbox Volumen", r'name="volume_filter"[^>]*checked'),
    ("Checkbox Macro H4", r'name="macro_trend_filter"[^>]*checked'),
    ("Checkbox Régimen ADX", r'name="regime_filter"[^>]*checked'),
    ("Checkbox Cierre Inteligente", r'name="max_duration_profit"[^>]*checked'),
    ("Checkbox Señal Opuesta", r'name="close_on_opposite"[^>]*checked'),
]

all_ok = True
for label, pattern in checks:
    if re.search(pattern, html):
        print(f"  ✅ {label}")
    else:
        print(f"  ❌ {label} (NO SE CARGÓ)")
        all_ok = False

print("-" * 70)
if all_ok:
    print("🏆 ¡TODAS LAS CONFIGURACIONES SE GUARDAN Y SE RETORNAN CORRECTAMENTE!")
else:
    print("⚠️ Algunas configuraciones NO se están guardando. Revisa los ❌.")

# Limpiar
subprocess.run(["php", "artisan", "tinker", "--execute", f"\\App\\Models\\Backtest::find({bt_id})->delete();"])
print("🧹 Backtest de prueba eliminado.")
