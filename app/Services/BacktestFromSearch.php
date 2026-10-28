<?php

namespace App\Services;

use App\Http\Controllers\BacktestingController;
use App\Models\Strategy;
use App\Models\User;
use DOMDocument;
use DOMXPath;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use RuntimeException;

/**
 * Ejecuta (y opcionalmente guarda) un backtest a partir de una configuración de la búsqueda por el MISMO camino que
 * el botón Ejecutar + Guardar de la pantalla: BacktestingController::executeAjax (payload a Python, métricas, firma)
 * → save_data del HTML de resultados (lo que enviaría el navegador; las estrellas se calculan en esa vista)
 * → BacktestingController::saveBacktest (firma HMAC, anti-duplicado, transacción).
 * Así lo creado desde la búsqueda es idéntico a un backtest hecho a mano.
 */
class BacktestFromSearch
{
    public function __construct(private readonly BacktestingController $controller,
                                private readonly StrategyConfigSync $sync)
    {
    }

    /** Campos del formulario tal como los envía run.blade.php (checkbox marcado = campo presente). */
    public static function formFields(array $cfg, int $strategyId, string $interval, array $symbols, int $months): array
    {
        $ambiguous = match (strtoupper((string) ($cfg['regime_ambiguous_as'] ?? 'RANGING'))) {
            'TRENDING'  => 'tendencia',
            'NO_OPERAR' => 'ignorar',
            default     => 'lateral',
        };
        $f = [
            'strategy_id'                    => $strategyId,
            'symbols'                        => array_values($symbols),
            'interval'                       => $interval,
            'months'                         => $months,
            'initial_balance'                => '10000',   // valor oculto por defecto del formulario
            'risk_per_trade_pct'             => '1.0',
            'commission_pct'                 => '0.055',
            'slippage_pct'                   => '0.05',
            'sl_pct'                         => (string) $cfg['sl_pct'],
            'tp_pct'                         => (string) $cfg['tp_pct'],
            'be_pct'                         => (string) $cfg['be_pct'],
            'max_duration'                   => (string) $cfg['max_duration'],
            'trailing_mode'                  => $cfg['trailing_mode'] ?: 'none',
            'trailing_distance_pct'          => (string) $cfg['trailing_distance_pct'],
            'trailing_activation_buffer_pct' => (string) $cfg['trailing_activation_buffer_pct'],
            'trailing_atr_mult'              => (string) $cfg['trailing_atr_mult'],
            'regime_adx_trending'            => (string) $cfg['regime_adx_trending'],
            'regime_adx_ranging'             => (string) $cfg['regime_adx_ranging'],
            'regime_ambiguous_as'            => $ambiguous,
            'volume_filter_period'           => (string) $cfg['volume_filter_period'],
            'volume_filter_mult'             => (string) $cfg['volume_filter_mult'],
            'volatility_protection_mode'     => 'none',
        ];
        foreach (['max_duration_profit', 'close_on_opposite', 'regime_filter', 'macro_trend_filter', 'volume_filter',
                  'btc_trend_filter'] as $cb) {
            if (! empty($cfg[$cb])) {
                $f[$cb] = 'on';
            }
        }

        return $f;
    }

    /**
     * @return array{payload: array, warnings: array, saved: ?array}
     *         payload = lo que se guarda (métricas por moneda incluidas); saved = respuesta del guardado o null.
     * @throws RuntimeException si el backtest o el guardado fallan
     */
    public function run(User $user, Strategy $strategy, array $cfg, string $interval, array $symbols, int $months, bool $save): array
    {
        $previousUser = Auth::user();
        $previousRequest = app('request');
        Auth::setUser($user);
        try {
            $fields = self::formFields($cfg, (int) $strategy->id, $interval, $symbols, $months);
            $body = $this->controller->executeAjax($this->bind(Request::create('/backtesting/execute-ajax', 'POST', $fields)))
                ->getData(true);
            if (empty($body['success'])) {
                throw new RuntimeException('El backtest falló: ' . ($body['error'] ?? 'error desconocido'));
            }
            $saveData = self::saveDataFromHtml($body['html'] ?? '');
            $payload = $saveData ? json_decode((string) base64_decode($saveData, true), true) : null;
            if (! is_array($payload)) {
                throw new RuntimeException('El resultado del backtest no trae los datos para guardar.');
            }

            $saved = null;
            if ($save) {
                $req = Request::create('/backtesting/save', 'POST', ['save_data' => $saveData]);
                $req->headers->set('Accept', 'application/json');
                $saved = $this->controller->saveBacktest($this->bind($req), $this->sync)->getData(true);
                if (empty($saved['success'])) {
                    throw new RuntimeException($saved['message'] ?? 'No se pudo guardar el backtest.');
                }
            }

            return ['payload' => $payload, 'warnings' => array_values(array_unique($body['warnings'] ?? [])), 'saved' => $saved];
        } finally {
            app()->instance('request', $previousRequest);
            $previousUser ? Auth::setUser($previousUser) : Auth::forgetUser();
        }
    }

    private function bind(Request $req): Request
    {
        $session = app('session')->driver();
        if (! $session->isStarted()) {
            $session->start();
        }
        $req->setLaravelSession($session);
        $req->setUserResolver(fn () => Auth::user());
        app()->instance('request', $req);

        return $req;
    }

    private static function saveDataFromHtml(string $html): ?string
    {
        $doc = new DOMDocument();
        libxml_use_internal_errors(true);
        $doc->loadHTML('<?xml encoding="utf-8"?>' . $html);
        libxml_clear_errors();
        $node = (new DOMXPath($doc))->query('//form[@id="saveBacktestForm"]//input[@name="save_data"]')->item(0);

        return $node?->getAttribute('value');
    }
}
