@extends('layouts.app')
@section('title', 'Avisos')
@section('header', 'Avisos')

@section('content')
<style>
    .nf-bar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 12px; }
    .nf-chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .nf-chip { border: 1px solid var(--color-border-soft); background: var(--color-surface); color: var(--color-text-secondary); border-radius: 999px;
               padding: 4px 10px; font-size: 11px; text-decoration: none; }
    .nf-chip.on { border-color: var(--color-info); background: rgba(77, 143, 232, .15); color: #BFD6F6; }
    .nf-card { background: var(--color-surface); border: 1px solid var(--color-border-soft); border-radius: 10px; overflow: hidden; }
    .nf-row { display: grid; grid-template-columns: 22px 1fr auto; gap: 10px; align-items: start; padding: 12px 16px; border-top: 1px solid var(--color-border-soft); font-size: 12px; }
    .nf-row:first-child { border-top: 0; }
    .nf-row.unread { background: rgba(139, 92, 246, .06); }
    .nf-row b { display: block; font-weight: 600; color: var(--color-text-primary); }
    .nf-row .b { display: block; color: var(--color-text-secondary); }
    .nf-row small { display: block; color: var(--color-text-muted); font-size: 10px; margin-top: 2px; }
    .nf-btn { border: 0; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 500; background: #374151; color: #e5e7eb; text-decoration: none; white-space: nowrap; cursor: pointer; }
    .nf-empty { padding: 24px 16px; text-align: center; color: var(--color-text-muted); font-size: 12px; }
    @media (max-width: 640px) { .nf-row { grid-template-columns: 22px 1fr; } .nf-row .nf-btn { grid-column: 2; justify-self: start; } }
</style>

<div class="nf-bar">
    <div class="nf-chips">
        <a class="nf-chip {{ ! $cat && ! $unread ? 'on' : '' }}" href="{{ route('notifications.index') }}">Todos</a>
        @foreach($categories as $key => $label)
            <a class="nf-chip {{ $cat === $key ? 'on' : '' }}" href="{{ route('notifications.index', ['c' => $key]) }}">{{ $label }}</a>
        @endforeach
        <a class="nf-chip {{ $unread ? 'on' : '' }}" href="{{ route('notifications.index', ['sin_leer' => 1]) }}">Sin leer ({{ $unreadCount }})</a>
    </div>
    @if($unreadCount > 0)
        <form method="POST" action="{{ route('notifications.read') }}">@csrf<button type="submit" class="nf-btn">Marcar todo como leído</button></form>
    @endif
</div>

<div class="nf-card">
    @forelse($items as $n)
        @php $p = \App\Http\Controllers\NotificationController::present($n); @endphp
        <div class="nf-row {{ $p['unread'] ? 'unread' : '' }}">
            <span style="font-size:14px;line-height:1.3">{{ $p['icon'] }}</span>
            <div><b>{{ $p['title'] }}</b>@if($p['body'] !== '')<span class="b">{{ $p['body'] }}</span>@endif<small>{{ $p['at'] }} · {{ $p['ago'] }}</small></div>
            @if($p['action'])<a class="nf-btn" href="{{ $p['url'] }}">{{ $p['action'] }}</a>@endif
        </div>
    @empty
        <div class="nf-empty">Sin avisos{{ $cat || $unread ? ' con este filtro' : '' }}. Se guardan los últimos 30 días.</div>
    @endforelse
</div>

@if($items->hasPages())
    <div style="margin-top:12px">{{ $items->links() }}</div>
@endif
<p style="margin-top:10px;font-size:11px;color:var(--color-text-muted)">Íconos: ⛔ error · ⚠️ advertencia · 🛠️ reparación · ✅ resuelto o terminado · ❌ búsqueda fallida · ℹ️ información. Se borran solos a los 30 días.</p>
@endsection
