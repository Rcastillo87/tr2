<?php
namespace App\Http\Controllers;

use App\Models\Strategy;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\ValidationException;

class StrategyController extends Controller
{
    public function index()
    {
        Gate::authorize('manageUsers');

        $strategies = Strategy::withCount('backtests')->orderBy('name')->get();
        
        // Obtener los Backtests reales que están en Paper
        $paperConfigs = \App\Models\PaperStrategyConfig::where('active', true)
            ->whereNotNull('backtest_id')
            ->get();
            
        $backtestIds = $paperConfigs->pluck('backtest_id')->unique();
        $backtests = \App\Models\Backtest::whereIn('id', $backtestIds)->get();
        
        $groupedPapers = [];
        foreach ($backtests as $bt) {
            $groupedPapers[$bt->strategy_id][] = $bt;
        }

        return view('strategies.index', compact('strategies', 'groupedPapers'));
    }

    public function create()
    {
        Gate::authorize('manageUsers');
        return view('strategies.form', ['strategy' => new Strategy()]);
    }

    public function store(Request $request)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'name' => 'required|string|max:100|unique:strategies,name',
            'description' => 'nullable|string|max:255',
            'code' => 'required|string',
            'config' => 'nullable|string',
        ]);

        if (!empty($validated['config'])) {
            $decoded = json_decode($validated['config'], true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                throw ValidationException::withMessages(['config' => 'El JSON de configuración no es válido.']);
            }
            $validated['config'] = $decoded;
        } else {
            $validated['config'] = [];
        }

        $this->runSmokeTest($validated['code']);

        try {
            Strategy::create($validated);
        } catch (\Throwable $e) {
            \Illuminate\Support\Facades\Log::error('Error creando estrategia: ' . $e->getMessage());
            throw \Illuminate\Validation\ValidationException::withMessages([
                'name' => 'Error al guardar en la base de datos: ' . $e->getMessage()
            ]);
        }
        
        if ($request->ajax() || $request->wantsJson()) {
            return response()->json(['success' => true, 'message' => 'Estrategia creada y validada correctamente.', 'redirect' => route('strategies.index')]);
        }
        return redirect()->route('strategies.index')->with('status', 'Estrategia creada y validada correctamente.');
    }

    public function edit(Strategy $strategy)
    {
        Gate::authorize('manageUsers');
        return view('strategies.form', compact('strategy'));
    }

    public function update(Request $request, Strategy $strategy)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'name' => 'required|string|max:100|unique:strategies,name,' . $strategy->id,
            'description' => 'nullable|string|max:255',
            'code' => 'required|string',
            'config' => 'nullable|string',
        ]);

        if (!empty($validated['config'])) {
            $decoded = json_decode($validated['config'], true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                throw ValidationException::withMessages(['config' => 'El JSON de configuración no es válido.']);
            }
            $validated['config'] = $decoded;
        } else {
            $validated['config'] = [];
        }

        $this->runSmokeTest($validated['code']);

        $strategy->update($validated);
        return redirect()->route('strategies.index')->with('status', 'Estrategia actualizada y validada correctamente.');
    }

    public function toggle(Strategy $strategy)
    {
        Gate::authorize('manageUsers');
        $strategy->active = !$strategy->active;
        $strategy->save();
        return back()->with('status', "Estrategia {$strategy->name} " . ($strategy->active ? 'activada' : 'desactivada'));
    }

    public function destroy(Strategy $strategy)
    {
        Gate::authorize('manageUsers');

        // Verificar si tiene configuraciones activas en Paper Trading
        $hasActivePaper = \App\Models\PaperStrategyConfig::where('active', true)
            ->where('display_name', 'like', $strategy->name . '%')
            ->exists();

        if ($hasActivePaper) {
            return back()->with('error', 'No puedes eliminar esta estrategia porque tiene una variante activa en Paper Trading. Pausa el Paper primero.');
        }
        $name = $strategy->name;
        $strategy->delete();
        return back()->with('status', "Estrategia {$name} eliminada.");
    }

    private function runSmokeTest($code)
    {
        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(30)->post(
                config('trading.python_engine_url') . '/v1/strategies/validate',
                ['code' => $code, 'type' => 'python', 'run_backtest' => true]
            );

            if (!$response->successful()) {
                $errorMsg = $response->json('detail') ?? 'Error desconocido en validación.';
                throw ValidationException::withMessages([
                    'code' => "❌ Falló el Smoke Test: " . $errorMsg
                ]);
            }

            $trades = $response->json('trades');
            if ($trades !== null && $trades == 0) {
                throw ValidationException::withMessages([
                    'code' => "❌ Falló el Smoke Test: La estrategia no abrió ninguna operación en el último mes. Revisa la lógica o los filtros."
                ]);
            }

        } catch (ValidationException $e) {
            throw $e;
        } catch (\Throwable $e) {
            throw ValidationException::withMessages([
                'code' => "❌ Error conectando al motor de validación: " . $e->getMessage()
            ]);
        }
    }
}
