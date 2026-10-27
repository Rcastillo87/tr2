<?php

return [
    'python_engine_url' => env('PYTHON_ENGINE_URL', 'http://127.0.0.1:8002'),
    'python_internal_api_key' => env('PYTHON_INTERNAL_API_KEY', ''),

    // Vigilante del collector (php artisan collector:watchdog, cada 5 min por cron). Reinicios apagados por defecto.
    'watchdog' => [
        'restart_engine'     => (bool) env('WATCHDOG_RESTART_ENGINE', false),
        'restart_horizon'    => (bool) env('WATCHDOG_RESTART_HORIZON', false),
        'fails_to_restart'   => (int) env('WATCHDOG_FAILS_TO_RESTART', 3),     // revisiones seguidas (x 5 min)
        'restart_cooldown_s' => (int) env('WATCHDOG_RESTART_COOLDOWN_S', 1800), // máx. 1 reinicio por servicio
        'queue_stale_s'      => (int) env('WATCHDOG_QUEUE_STALE_S', 300),       // cola sin correr el collector
        'series_grace_s'     => (int) env('WATCHDOG_SERIES_GRACE_S', 300),      // atraso > 1 vela + margen
        'real_tick_stale_s'  => (int) env('WATCHDOG_REAL_TICK_STALE_S', 180),   // real: posiciones sin tick reciente
    ],
    // Avisos de broker (php artisan broker:events, cada minuto por cron)
    'broker_events' => [
        'retention_days'   => (int) env('BROKER_EVENTS_RETENTION_DAYS', 90),  // rastro forense
        'throttle_minutes' => (int) env('BROKER_EVENTS_THROTTLE_MINUTES', 60), // mismo problema repetido
    ],
    'allow_investor_demo_accounts' => env('ALLOW_INVESTOR_DEMO_ACCOUNTS', false),
];
