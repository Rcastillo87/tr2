<?php

namespace App\Http\Controllers;

use App\Models\CollectorConfig;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class CollectorConfigController extends Controller
{


    public function unified(Request $request)
    {
        Gate::authorize('manageUsers');

        $filters = $request->only(['broker', 'symbol']);
        $data = [];
        $debug = null;

        try {
            $url = config('trading.python_engine_url') . '/v1/collector/unified';
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(45)->get($url, $filters);

            if ($response->successful()) {
                $data = $response->json('data') ?? [];
            } else {
                $debug = "HTTP {$response->status()}: {$response->body()}";
                Log::error("Unified HTTP error: $debug");
            }
        } catch (\Throwable $e) {
            $debug = $e->getMessage();
            Log::error('Unified exception: ' . $debug);
        }

        return view('data-collector.index', [
            'rows'            => $data,
            'filters'         => $filters,
            'debug'           => $debug,
            'lastRun'         => \Illuminate\Support\Facades\Cache::get(\App\Jobs\CollectOhlcvDataJob::LAST_RUN_KEY),
            'validation'      => \Illuminate\Support\Facades\Cache::get(\App\Jobs\ValidateCollectorDataJob::RESULT_KEY),
            'validating'      => \Illuminate\Support\Facades\Cache::has(\App\Jobs\ValidateCollectorDataJob::RUNNING_KEY),
            'validationError' => \Illuminate\Support\Facades\Cache::get(\App\Jobs\ValidateCollectorDataJob::ERROR_KEY),
        ]);
    }

    /** "Validar contra Bybit": encola la validación (cola research, 1 proceso). */
    public function validateData()
    {
        Gate::authorize('manageUsers');
        $cache = \Illuminate\Support\Facades\Cache::store();
        if (! $cache->add(\App\Jobs\ValidateCollectorDataJob::RUNNING_KEY, now()->toIso8601String(), now()->addMinutes(25))) {
            return response()->json(['ok' => true, 'running' => true, 'since' => $cache->get(\App\Jobs\ValidateCollectorDataJob::RUNNING_KEY)]);
        }
        \App\Jobs\ValidateCollectorDataJob::dispatch()
            ->onConnection(\App\Services\ParamSearchService::QUEUE_CONNECTION)->onQueue(\App\Services\ParamSearchService::QUEUE);

        return response()->json(['ok' => true, 'running' => true, 'since' => now()->toIso8601String()]);
    }

    public function validationStatus()
    {
        Gate::authorize('manageUsers');
        $v = \Illuminate\Support\Facades\Cache::get(\App\Jobs\ValidateCollectorDataJob::RESULT_KEY);

        return response()->json([
            'running' => \Illuminate\Support\Facades\Cache::has(\App\Jobs\ValidateCollectorDataJob::RUNNING_KEY),
            'at'      => $v['at'] ?? null,
            'summary' => $v['summary'] ?? null,
            'error'   => \Illuminate\Support\Facades\Cache::get(\App\Jobs\ValidateCollectorDataJob::ERROR_KEY),
        ]);
    }

    public function toggleAll(Request $request, string $broker, string $symbol)
    {
        Gate::authorize('manageUsers');

        $active = $request->boolean('active');

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->post(
                config('trading.python_engine_url') . "/v1/collector/toggle-all/{$broker}/{$symbol}?active=" . ($active ? 'true' : 'false')
            );

            if (!$response->successful()) {
                return back()->withErrors(['toggle' => $response->json('detail') ?? 'Error del motor']);
            }

            $count = $response->json('updated', 0);
            return back()->with('status', "{$symbol}: {$count} intervalo(s) " . ($active ? 'activados' : 'desactivados'));
        } catch (\Throwable $e) {
            return back()->withErrors(['toggle' => 'Error: ' . $e->getMessage()]);
        }
    }

    public function toggleOne(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'broker'   => 'required|string',
            'symbol'   => 'required|string',
            'interval' => 'required|string',
            'active'   => 'required|boolean',
        ]);

        try {
            $config = \App\Models\CollectorConfig::where('broker', $validated['broker'])
                ->where('symbol', $validated['symbol'])
                ->where('interval', $validated['interval'])
                ->first();

            if (!$config) {
                return response()->json(['ok' => false, 'error' => 'Config no encontrada'], 404);
            }

            $config->active = $validated['active'];
            $config->save();

            return response()->json(['ok' => true, 'active' => $config->active]);
        } catch (\Throwable $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 500);
        }
    }

    public function backfill(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'symbol'     => ['required', 'string'],
            'interval'   => ['required', 'string'],
            'broker'     => ['required', 'string'],
            'start_date' => ['required', 'date'],
            'end_date'   => ['nullable', 'date', 'after:start_date'],
        ]);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(300)->post(
                config('trading.python_engine_url') . '/v1/collector/backfill',
                $validated
            );

            if (!$response->successful()) {
                return response()->json([
                    'ok' => false,
                    'error' => $response->json('detail') ?? 'Error del motor',
                ], 500);
            }

            return response()->json(['ok' => true] + $response->json());
        } catch (\Throwable $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 500);
        }
    }

    public function invalidate(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'symbol'     => ['required', 'string'],
            'interval'   => ['required', 'string'],
            'broker'     => ['required', 'string'],
            'start_date' => ['nullable', 'date'],
            'end_date'   => ['nullable', 'date', 'after_or_equal:start_date'],
            'confirm'    => ['required', 'in:CONFIRMAR'],
        ]);

        $payload = array_merge(
            $validated,
            ['confirm' => true]
        );
        unset($payload['confirm_string']);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(60)->post(
                config('trading.python_engine_url') . '/v1/collector/invalidate',
                $payload
            );

            if (!$response->successful()) {
                return response()->json([
                    'ok' => false,
                    'error' => $response->json('detail') ?? 'Error del motor',
                ], 500);
            }

            return response()->json(['ok' => true] + $response->json());
        } catch (\Throwable $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 500);
        }
    }

    public function reload(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'symbol'   => ['required', 'string'],
            'interval' => ['required', 'string'],
            'broker'   => ['required', 'string'],
            'confirm'  => ['required', 'in:CONFIRMAR'],
        ]);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(600)->post(
                config('trading.python_engine_url') . "/v1/collector/reload/{$validated['symbol']}/{$validated['interval']}/{$validated['broker']}?confirm=true"
            );

            if (!$response->successful()) {
                return response()->json([
                    'ok' => false,
                    'error' => $response->json('detail') ?? 'Error del motor',
                ], 500);
            }

            return response()->json(['ok' => true] + $response->json());
        } catch (\Throwable $e) {
            return response()->json(['ok' => false, 'error' => $e->getMessage()], 500);
        }
    }

    public function addSymbol(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'symbol'    => ['required', 'string', 'max:20'],
            'broker'    => ['required', 'string', 'in:bybit'],
            'intervals' => ['required', 'array', 'min:1'],
            'intervals.*' => ['string'],
        ]);

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(15)->post(
                config('trading.python_engine_url') . '/v1/collector/add-symbol',
                array_merge($validated, ['active' => true])
            );

            if (!$response->successful()) {
                return back()->withErrors([
                    'symbol' => $response->json('detail') ?? 'Error del motor',
                ]);
            }

            $inserted = $response->json('inserted', 0);
            return back()->with('status',
                "{$validated['symbol']} agregado con {$inserted} intervalo(s)."
            );
        } catch (\Throwable $e) {
            return back()->withErrors(['symbol' => 'Error: ' . $e->getMessage()]);
        }
    }

    public function toggleActive(CollectorConfig $config)
    {
        Gate::authorize('manageUsers');

        $config->active = !$config->active;
        $config->save();

        return back()->with('status',
            ($config->active ? 'Activado' : 'Desactivado') . ": {$config->symbol}/{$config->interval}"
        );
    }
}
