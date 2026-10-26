#!/bin/bash
cd /home/tr2/htdocs/tr2.srv685835.hstgr.cloud
eval "$(php -r '
require "vendor/autoload.php";
$app = require "bootstrap/app.php";
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$db = config("database.connections.pgsql");
echo "export DB_HOST=" . escapeshellarg($db["host"]) . "\n";
echo "export DB_PORT=" . escapeshellarg($db["port"]) . "\n";
echo "export DB_DATABASE=" . escapeshellarg($db["database"]) . "\n";
echo "export DB_USERNAME=" . escapeshellarg($db["username"]) . "\n";
echo "export PGPASSWORD=" . escapeshellarg($db["password"]) . "\n";
')"
exec psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" "$@"
