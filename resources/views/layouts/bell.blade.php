{{-- Campana de avisos (cabecera). $unreadAlerts lo calcula layouts/app. El panel y su script están en layouts/bell-panel. --}}
<button type="button" class="tr-bell" onclick="trBellToggle(event)" title="Avisos" aria-label="Avisos">🔔@if(($unreadAlerts ?? 0) > 0)<i class="tr-bell-n">{{ $unreadAlerts > 99 ? '99+' : $unreadAlerts }}</i>@endif</button>
