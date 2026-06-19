<?php

namespace App\Http\Controllers;

use App\Models\CollectorConfig;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Gate;

class CollectorConfigController extends Controller
{
    public function index()
    {
        Gate::authorize('manageUsers'); // solo admin

        $configs = CollectorConfig::orderBy('symbol')->orderBy('interval')->get();

        // Agrupar por simbolo para mostrar en la vista
        $grouped = $configs->groupBy('symbol');

        return view('data-collector.configs', compact('grouped'));
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
