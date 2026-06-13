<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class DataCollectorController extends Controller
{
    public function index()
    {
        $status = [];

        try {
            $response = Http::withHeaders([
                'X-Internal-API-Key' => config('trading.python_internal_api_key'),
            ])->timeout(10)->get(config('trading.python_engine_url') . '/v1/collector/status');

            if ($response->successful()) {
                $status = $response->json('data') ?? [];
            }
        } catch (\Throwable $e) {
            Log::warning('DataCollector: error obteniendo estado — ' . $e->getMessage());
        }

        return view('data-collector.index', ['status' => $status]);
    }
}
