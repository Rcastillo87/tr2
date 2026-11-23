<?php
/**
 * C5-09 (integración, Laravel + base real): matriz dinámica de permisos por rol (D-46) y aislamiento entre usuarios.
 * Recorre TODAS las rutas web de la aplicación con cada perfil y comprueba que:
 *  - visitante sin sesión: ninguna ruta protegida responde (redirige al login o 403);
 *  - usuario inactivo (aunque sea admin): se le cierra la sesión y va al login (D-02);
 *  - cada rol: las rutas que NO le corresponden responden 403 (todos los métodos); las GET que SÍ le corresponden abren
 *    (no 401/403/419 ni redirección al login). Las acciones que escriben (POST/PATCH/PUT/DELETE) no se ejecutan con los
 *    roles autorizados: solo se comprueba que se niegan a los demás;
 *  - aislamiento: un inversionista no puede tocar ni ver la cuenta, las suscripciones ni los avisos de otro.
 * TODO corre dentro de una transacción que se revierte (usuarios, cuentas y avisos de prueba incluidos): no deja cambios.
 * No llama al motor ni a Bybit (Http::fake), no encola trabajos (Bus/Queue::fake) ni manda avisos (Notification::fake).
 * Las sesiones van en memoria (array). No imprime credenciales.
 * Uso (servidor): cd <raíz del proyecto> && php tests/Forensic/role_matrix_test.php
 */

declare(strict_types=1);

require getcwd() . '/vendor/autoload.php';
$app = require getcwd() . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use App\Models\Backtest;
use App\Models\BrokerAccount;
use App\Models\ParamSearchRun;
use App\Models\RealStrategySubscription;
use App\Models\Strategy;
use App\Models\User;
use Illuminate\Foundation\Http\Middleware\ValidateCsrfToken;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Notification;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Str;

$fails = 0;
$warns = [];
$check = function (string $name, bool $ok, string $detail = '') use (&$fails): void {
    $fails += $ok ? 0 : 1;
    if (! $ok || getenv('VERBOSE')) {
        printf("%s  %s%s\n", $ok ? 'PASS' : 'FAIL', $name, $detail !== '' ? "  -> {$detail}" : '');
    }
};

// ── Aislamiento del entorno de la prueba ──
config(['session.driver' => 'array', 'queue.default' => 'sync']);
Http::fake(['*' => Http::response(['status' => 'ok'], 200)]);
Bus::fake();
Queue::fake();
Notification::fake();
Mail::fake();
ValidateCsrfToken::except(['*']);   // las peticiones de la prueba no traen token; la autorización se prueba igual

// D-46: qué rol abre cada grupo de rutas (por nombre). Lo que no está aquí no es parte de la matriz (login, etc.).
const ALL = ['admin', 'consultor', 'inversionista'];
$expected = function (string $name): ?array {
    $map = [
        'dashboard' => ALL, 'notifications.' => ALL, 'profile.' => ALL,
        'paper-trading.' => ['admin', 'consultor'],
        'trading.' => ['admin', 'inversionista'],
        'backtesting.' => ['admin'], 'strategies.' => ['admin'], 'users.' => ['admin'], 'collector.' => ['admin'],
    ];
    foreach ($map as $prefix => $roles) {
        if ($name === $prefix || str_starts_with($name, $prefix)) {
            return $roles;
        }
    }

    return null;
};

DB::beginTransaction();
try {
    $tag = 'c509-' . Str::lower(Str::random(6));
    $mk = fn (string $role, bool $active = true) => User::forceCreate([
        'name' => "{$tag} {$role}", 'email' => "{$tag}-{$role}-" . Str::random(4) . '@test.invalid',
        'password' => bcrypt(Str::random(24)), 'role' => $role, 'is_active' => $active,
    ]);
    $users = ['admin' => $mk('admin'), 'consultor' => $mk('consultor'), 'inversionista' => $mk('inversionista')];
    $invB = $mk('inversionista');
    $inactive = $mk('admin', false);

    $account = fn (User $u, string $label) => BrokerAccount::forceCreate([
        'user_id' => $u->id, 'broker' => 'bybit', 'account_type' => 'demo', 'label' => $label,
        'api_key' => 'k-' . Str::random(8), 'api_secret' => 's-' . Str::random(8), 'status' => 'paused',
    ]);
    $accA = $account($users['inversionista'], "{$tag}-cuenta-A");
    $accB = $account($invB, "{$tag}-cuenta-B");
    $sub = fn (BrokerAccount $a, User $u) => RealStrategySubscription::forceCreate([
        'user_id' => $u->id, 'broker_account_id' => $a->id, 'strategy' => "{$tag} estrategia", 'symbol' => 'BTCUSDT',
        'interval' => '240', 'status' => 'paused',
    ]);
    $subA = $sub($accA, $users['inversionista']);
    $subB = $sub($accB, $invB);
    DB::table('notifications')->insert([
        'id' => (string) Str::uuid(), 'type' => 'c509', 'notifiable_type' => User::class, 'notifiable_id' => $invB->id,
        'data' => json_encode(['title' => "{$tag}-aviso-de-B", 'body' => 'privado']), 'created_at' => now(), 'updated_at' => now(),
    ]);

    $strategy = Strategy::query()->orderBy('id')->first();
    $backtest = Backtest::query()->orderBy('id')->first();
    $run = ParamSearchRun::query()->orderBy('id')->first();
    $params = [
        'strategy' => $strategy?->id, 'backtest' => $backtest?->id, 'run' => $run?->id, 'user' => $invB->id,
        'account' => $accA->id, 'subscription' => $subA->id, 'symbol' => 'BTCUSDT', 'interval' => '60', 'broker' => 'bybit',
    ];

    $kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);
    $call = function (string $method, string $uri, ?User $as, array $data = []) use ($app, $kernel) {
        $app['auth']->forgetGuards();
        if ($as) {
            $app['auth']->guard('web')->setUser($as);
        }
        $req = Request::create($uri, $method, $data, [], [], ['HTTP_ACCEPT' => 'text/html']);
        DB::beginTransaction();   // punto de guardado por petición: un error SQL no contamina la siguiente
        try {
            $res = $kernel->handle($req);
            $kernel->terminate($req, $res);
        } finally {
            DB::rollBack();
        }

        return $res;
    };
    $toLogin = fn ($res) => $res->isRedirect() && str_contains((string) $res->headers->get('Location'), '/login');
    $denied = fn ($res) => $res->getStatusCode() === 403;
    $opened = fn ($res) => ! in_array($res->getStatusCode(), [401, 403, 419], true) && ! $toLogin($res);

    // Rutas de la matriz
    $routes = [];
    foreach (Route::getRoutes() as $r) {
        $name = (string) $r->getName();
        $roles = $expected($name);
        if ($roles === null) {
            continue;
        }
        $missing = [];
        $uri = preg_replace_callback('/\{(\w+)(\?)?\}/', function ($m) use ($params, &$missing) {
            $v = $params[$m[1]] ?? null;
            if ($v === null) {
                $missing[] = $m[1];
            }

            return (string) ($v ?? '');
        }, $r->uri());
        foreach ($r->methods() as $method) {
            if ($method === 'HEAD') {
                continue;
            }
            $routes[] = ['name' => $name, 'method' => $method, 'uri' => '/' . ltrim((string) $uri, '/'), 'roles' => $roles,
                'missing' => $missing];
        }
    }
    $check('M0: la matriz cubre las rutas de la aplicación (≥ 60 combinaciones de ruta y método)', count($routes) >= 60,
        (string) count($routes));
    foreach ($routes as $rt) {
        if ($rt['missing']) {
            $warns[] = "{$rt['method']} {$rt['name']}: sin dato de prueba para {" . implode(',', $rt['missing']) . '}: no se prueba';
        }
    }
    $routes = array_values(array_filter($routes, fn ($rt) => ! $rt['missing']));

    $counts = ['guest' => 0, 'inactive' => 0, 'denied' => 0, 'opened' => 0, 'skipped_write' => 0];
    foreach ($routes as $rt) {
        $label = "{$rt['method']} {$rt['uri']} ({$rt['name']})";
        // visitante
        $res = $call($rt['method'], $rt['uri'], null);
        $check("G: visitante no entra a {$label}", $toLogin($res) || $denied($res), (string) $res->getStatusCode());
        $counts['guest']++;
        // inactivo (admin): sesión cerrada y al login
        $res = $call($rt['method'], $rt['uri'], $inactive);
        $check("I: usuario inactivo no entra a {$label}", $toLogin($res), (string) $res->getStatusCode());
        $counts['inactive']++;
        foreach ($users as $role => $u) {
            $allowed = in_array($role, $rt['roles'], true);
            if (! $allowed) {
                $res = $call($rt['method'], $rt['uri'], $u);
                $check("D: {$role} recibe 403 en {$label}", $denied($res), (string) $res->getStatusCode());
                $counts['denied']++;
            } elseif ($rt['method'] === 'GET') {
                $res = $call('GET', $rt['uri'], $u);
                $code = $res->getStatusCode();
                $check("A: {$role} abre {$label}", $opened($res), (string) $code);
                if ($code >= 500 || $code === 404) {
                    $warns[] = "{$role} GET {$rt['name']}: HTTP {$code} (autorizado; la página no cargó con los datos de prueba)";
                }
                $counts['opened']++;
            } else {
                $counts['skipped_write']++;
            }
        }
    }

    // ── Aislamiento entre inversionistas (A no toca ni ve lo de B) ──
    $A = $users['inversionista'];
    $foreign = [
        ['PATCH', "/trading/accounts/{$accB->id}/toggle-status"], ['PATCH', "/trading/accounts/{$accB->id}/limits"],
        ['DELETE', "/trading/accounts/{$accB->id}"], ['POST', "/trading/accounts/{$accB->id}/subscriptions"],
        ['POST', "/trading/accounts/{$accB->id}/subscriptions/all"],
        ['PATCH', "/trading/accounts/{$accB->id}/subscriptions/{$subB->id}/toggle"],
        ['DELETE', "/trading/accounts/{$accB->id}/subscriptions/{$subB->id}"],
        // suscripción de B colgada de la cuenta de A (id cruzado)
        ['PATCH', "/trading/accounts/{$accA->id}/subscriptions/{$subB->id}/toggle"],
        ['DELETE', "/trading/accounts/{$accA->id}/subscriptions/{$subB->id}"],
    ];
    foreach ($foreign as [$m, $uri]) {
        $res = $call($m, $uri, $A);
        $check("X: inversionista A no puede {$m} {$uri} (de B)", $denied($res), (string) $res->getStatusCode());
    }
    $before = [$accB->fresh()->status, $accB->fresh()->label, RealStrategySubscription::whereKey($subB->id)->exists()];
    $check('X: la cuenta y la suscripción de B siguen igual', $before === ['paused', "{$tag}-cuenta-B", true], json_encode($before));
    foreach (['/trading', "/trading?account={$accB->id}", '/trading/accounts', '/trading/live-prices', '/'] as $uri) {
        $body = (string) $call('GET', $uri, $A)->getContent();
        $check("V: A no ve la cuenta de B en {$uri}", ! str_contains($body, "{$tag}-cuenta-B"));
    }
    $body = (string) $call('GET', '/trading/accounts', $A)->getContent();
    $check('V: A sí ve su propia cuenta en /trading/accounts (la prueba de arriba no es vacía)', str_contains($body, "{$tag}-cuenta-A"));
    foreach (['/avisos', '/avisos/recientes'] as $uri) {
        $body = (string) $call('GET', $uri, $A)->getContent();
        $check("V: A no ve los avisos de B en {$uri}", ! str_contains($body, "{$tag}-aviso-de-B"));
    }
    $body = (string) $call('GET', '/trading/accounts', $users['admin'])->getContent();
    $check('V: el admin tampoco ve en Real las cuentas de otros (Real es por usuario)', ! str_contains($body, "{$tag}-cuenta-B"));

    printf("\nMatriz: %d rutas·método · visitante %d · inactivo %d · denegadas %d · abiertas %d · escrituras autorizadas sin ejecutar %d\n",
        count($routes), $counts['guest'], $counts['inactive'], $counts['denied'], $counts['opened'], $counts['skipped_write']);
    foreach (array_unique($warns) as $w) {
        echo "AVISO  {$w}\n";
    }
} finally {
    DB::rollBack();
}

echo "\nRESULTADO: " . ($fails ? "{$fails} FALLO(S)" : 'TODO OK') . "\n";
exit($fails ? 1 : 0);
