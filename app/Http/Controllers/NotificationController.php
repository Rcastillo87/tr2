<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Notifications\DatabaseNotification;

/**
 * Avisos en la plataforma (campana 🔔 y página "Avisos"). Cada usuario ve solo los suyos: los del sistema llegan al
 * admin; los de broker, al dueño de la cuenta (App\Services\SystemAlerts).
 */
class NotificationController extends Controller
{
    public const CATEGORIES = ['collector' => 'Collector', 'validation' => 'Validación', 'repair' => 'Reparación',
                               'search' => 'Búsquedas', 'broker' => 'Broker'];
    private const PER_PAGE = 50;
    private const RECENT = 8;

    public function index(Request $request)
    {
        $user = $request->user();
        $cat = array_key_exists((string) $request->query('c'), self::CATEGORIES) ? (string) $request->query('c') : null;
        $unread = $request->boolean('sin_leer');
        $query = $user->notifications();
        if ($cat) {
            $query->whereRaw("data::jsonb->>'category' = ?", [$cat]);
        }
        if ($unread) {
            $query->whereNull('read_at');
        }

        return view('notifications.index', [
            'items'       => $query->paginate(self::PER_PAGE)->withQueryString(),
            'categories'  => self::CATEGORIES,
            'cat'         => $cat,
            'unread'      => $unread,
            'unreadCount' => $user->unreadNotifications()->count(),
        ]);
    }

    /** Desplegable de la campana: últimos avisos + no leídos. */
    public function recent(Request $request): JsonResponse
    {
        $user = $request->user();

        return response()->json([
            'unread' => $user->unreadNotifications()->count(),
            'items'  => $user->notifications()->limit(self::RECENT)->get()->map(fn ($n) => self::present($n))->values(),
        ]);
    }

    /** Marca todos como leídos (al abrir la campana o con el botón de la página). */
    public function markRead(Request $request): JsonResponse|RedirectResponse
    {
        $request->user()->unreadNotifications()->update(['read_at' => now()]);

        return $request->expectsJson() ? response()->json(['success' => true]) : back();
    }

    public static function present(DatabaseNotification $n): array
    {
        $d = (array) $n->data;

        return [
            'id'     => $n->id,
            'title'  => (string) ($d['title'] ?? 'Aviso'),
            'body'   => (string) ($d['body'] ?? ''),
            'url'    => $d['url'] ?? null,
            'action' => self::action($d['url'] ?? null),
            'icon'   => self::icon($d),
            'level'  => $d['level'] ?? 'info',
            'unread' => $n->read_at === null,
            'ago'    => $n->created_at?->locale('es')->diffForHumans(),
            'at'     => $n->created_at?->timezone(config('app.timezone'))->locale('es')->isoFormat('D MMM HH:mm'),
        ];
    }

    public static function icon(array $d): string
    {
        $level = $d['level'] ?? 'info';
        $cat = $d['category'] ?? '';

        return match (true) {
            $cat === 'repair'                       => '🛠️',
            $cat === 'search' && $level === 'error' => '❌',
            $level === 'error'                      => '⛔',
            $level === 'warning'                    => '⚠️',
            $level === 'success'                    => '✅',
            default                                 => 'ℹ️',
        };
    }

    public static function action(?string $url): ?string
    {
        return match (true) {
            $url === null || $url === ''              => null,
            str_contains($url, '/collector')          => 'Ver Data Collector',
            str_contains($url, '/strategies/busquedas') => 'Ver resultados',
            default                                   => 'Ver',
        };
    }
}
