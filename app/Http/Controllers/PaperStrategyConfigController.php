<?php

namespace App\Http\Controllers;

use App\Models\PaperStrategyConfig;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class PaperStrategyConfigController extends Controller
{
    public function index()
    {
        Gate::authorize('manageUsers'); // solo admin

        $configs = PaperStrategyConfig::orderBy('strategy_class')->orderBy('symbol')->get();

        return view('paper-trading.configs.index', compact('configs'));
    }

    public function toggleActive(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');

        $config->active = !$config->active;
        $config->save();

        return back()->with('status', $config->active
            ? "Configuración \"{$config->display_name}\" activada."
            : "Configuración \"{$config->display_name}\" desactivada.");
    }

    public function edit(PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');

        return view('paper-trading.configs.edit', compact('config'));
    }

    public function update(Request $request, PaperStrategyConfig $config)
    {
        Gate::authorize('manageUsers');

        $validated = $request->validate([
            'display_name' => ['required', 'string', 'max:100'],
            'interval'     => ['required', 'string', 'max:10'],
            'params'       => ['required', 'string'], // JSON como string desde el textarea
        ]);

        // Validar que params sea JSON valido
        $params = json_decode($validated['params'], true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            return back()->withErrors(['params' => 'Los parámetros no son JSON válido.']);
        }

        $config->update([
            'display_name' => $validated['display_name'],
            'interval'     => $validated['interval'],
            'params'       => $params,
        ]);

        return redirect()->route('paper-trading.configs.index')
            ->with('status', "Configuración \"{$config->display_name}\" actualizada.");
    }
}
