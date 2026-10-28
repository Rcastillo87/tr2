{{-- Límites de riesgo por cuenta (App\Services\RiskLimits). Estilos en línea: Tailwind está compilado. --}}
@if ($accounts->isNotEmpty())
@php
    $rl = config('trading.risk_limits');
    $stateStyle = ['ok' => ['Opera normal', 'var(--color-profit)'], 'full' => ['Sin entradas nuevas', 'var(--color-neutral)'], 'blocked' => ['Bloqueada', 'var(--color-loss)']];
@endphp
<div style="background:var(--color-surface); border:1px solid var(--color-border-soft); border-radius:8px; margin-bottom:16px;">
    <div style="display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:4px 12px; padding:8px 14px; border-bottom:1px solid var(--color-border-soft);">
        <span style="font-size:11px; font-weight:600; color:var(--color-text-secondary);">Límites de riesgo</span>
        <span style="font-size:10px; color:var(--color-text-muted);">Pérdida neta del mes (cerrados, % del saldo inicial) · trades abiertos · solo bloquean entradas</span>
    </div>
    @foreach ($accounts as $account)
        @php
            $r = $risk[$account->id];
            [$stateLabel, $stateColor] = $stateStyle[$r['state']];
            $lossColor = $r['state'] === 'blocked' ? 'var(--color-loss)' : ($r['loss_use'] >= 80 ? 'var(--color-neutral)' : 'var(--color-profit)');
            $openColor = $r['open_use'] >= 100 ? 'var(--color-neutral)' : 'var(--color-profit)';
        @endphp
        <div style="padding:8px 14px; {{ $loop->last ? '' : 'border-bottom:1px solid var(--color-border-soft);' }}">
            <div style="display:flex; flex-wrap:wrap; align-items:center; gap:6px 18px; font-size:11px; color:var(--color-text-secondary);">
                <span style="font-weight:600; color:var(--color-text-primary); min-width:86px;">{{ $account->label }}</span>
                <span style="display:inline-flex; align-items:center; gap:6px;">
                    Mes <span class="font-mono" style="color:{{ $r['pct'] !== null && $r['pct'] > 0 ? 'var(--color-profit)' : ($r['state'] === 'blocked' ? 'var(--color-loss)' : 'var(--color-text-primary)') }};">{{ $r['pct_text'] }}</span>
                    <span style="color:var(--color-text-muted);">/ −{{ rtrim(rtrim(number_format($r['max_loss'], 2, ',', ''), '0'), ',') }} %</span>
                    <span role="img" aria-label="Uso del límite mensual {{ round($r['loss_use']) }} %" style="display:inline-block; width:48px; height:4px; border-radius:2px; background:var(--color-border-strong); overflow:hidden;"><span style="display:block; height:4px; width:{{ max(2, round($r['loss_use'])) }}%; background:{{ $lossColor }};"></span></span>
                </span>
                <span style="display:inline-flex; align-items:center; gap:6px;">
                    Abiertos <span class="font-mono" style="color:var(--color-text-primary);">{{ $r['open'] }}</span>
                    <span style="color:var(--color-text-muted);">/ {{ $r['max_open'] }}</span>
                    <span role="img" aria-label="{{ $r['open'] }} de {{ $r['max_open'] }} trades abiertos" style="display:inline-block; width:48px; height:4px; border-radius:2px; background:var(--color-border-strong); overflow:hidden;"><span style="display:block; height:4px; width:{{ max(2, round($r['open_use'])) }}%; background:{{ $openColor }};"></span></span>
                </span>
                <span style="display:inline-flex; align-items:center; gap:5px; color:{{ $stateColor }};"><span style="width:6px; height:6px; border-radius:50%; background:{{ $stateColor }};"></span>{{ $stateLabel }}</span>
                <button type="button" onclick="toggleRiskEdit({{ $account->id }})" style="margin-left:auto; font-size:10px; padding:3px 10px; border-radius:4px; border:1px solid var(--color-border-strong); background:transparent; color:var(--color-text-secondary);">Editar</button>
            </div>
            @if ($r['note'] !== '')
                <div style="font-size:10px; margin-top:3px; color:var(--color-text-muted);">{{ $r['note'] }}</div>
            @endif
            <form id="risk-edit-{{ $account->id }}" method="POST" action="{{ route('trading.accounts.limits', $account) }}" onsubmit="showSaving()"
                  style="display:none; flex-wrap:wrap; align-items:flex-end; gap:8px 12px; margin-top:8px;">
                @csrf @method('PATCH')
                <label style="display:flex; flex-direction:column; gap:3px; font-size:10px; color:var(--color-text-muted);">
                    Pérdida máx. del mes ({{ $rl['monthly_loss_min'] }}–{{ $rl['monthly_loss_max'] }} %)
                    <input type="number" name="max_monthly_loss_pct" value="{{ $r['max_loss'] + 0 }}" min="{{ $rl['monthly_loss_min'] }}" max="{{ $rl['monthly_loss_max'] }}" step="0.5" required
                           class="font-mono" style="width:90px; padding:5px 8px; border-radius:6px; border:1px solid var(--color-border-strong); background:var(--color-surface-raised); color:var(--color-text-primary); font-size:12px;">
                </label>
                <label style="display:flex; flex-direction:column; gap:3px; font-size:10px; color:var(--color-text-muted);">
                    Trades abiertos máx. ({{ $rl['open_trades_min'] }}–{{ $rl['open_trades_max'] }})
                    <input type="number" name="max_open_trades" value="{{ $r['max_open'] }}" min="{{ $rl['open_trades_min'] }}" max="{{ $rl['open_trades_max'] }}" step="1" required
                           class="font-mono" style="width:90px; padding:5px 8px; border-radius:6px; border:1px solid var(--color-border-strong); background:var(--color-surface-raised); color:var(--color-text-primary); font-size:12px;">
                </label>
                <button type="submit" style="font-size:11px; font-weight:600; padding:6px 14px; border-radius:6px; border:none; background:var(--color-info); color:#fff;">Guardar</button>
                <button type="button" onclick="toggleRiskEdit({{ $account->id }})" style="font-size:11px; padding:6px 12px; border-radius:6px; border:1px solid var(--color-border-strong); background:transparent; color:var(--color-text-secondary);">Cancelar</button>
            </form>
        </div>
    @endforeach
</div>
<script>
function toggleRiskEdit(id) {
    const f = document.getElementById('risk-edit-' + id);
    if (f) f.style.display = f.style.display === 'flex' ? 'none' : 'flex';
}
</script>
@endif
