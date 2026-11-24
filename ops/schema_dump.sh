#!/bin/bash
# Vuelca la ESTRUCTURA del esquema public (sin datos, dueños ni permisos) a la salida estándar. Solo lectura.
# Uso (servidor): bash ops/schema_dump.sh > database/schema/pgsql-schema.sql
# TimescaleDB: pg_dump -n public no recrea las hypertables ni sus políticas; van como comentario en la cabecera.
set -euo pipefail
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
export PGOPTIONS='-c default_transaction_read_only=on'
q(){ psql -X -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" -tA -c "$1"; }
echo "-- Esquema public de TR2 (solo estructura). Generado con ops/schema_dump.sh — no editar a mano."
echo "-- PostgreSQL $(q 'SHOW server_version') · TimescaleDB $(q "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")"
echo "-- Hypertables (recrear con create_hypertable después de crear la tabla):"
q "SELECT '--   ' || hypertable_name || ' por ' || column_name || ' cada ' || time_interval FROM timescaledb_information.dimensions ORDER BY 1" 
echo "-- Políticas de TimescaleDB:"
q "SELECT '--   ' || proc_name || ' en ' || hypertable_name || ' cada ' || schedule_interval || ' ' || config::text FROM timescaledb_information.jobs WHERE hypertable_name IS NOT NULL ORDER BY job_id"
echo "-- Migraciones SQL aplicadas después: database/sql-migrations (este volcado ya las incluye)."
echo
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USERNAME" -d "$DB_DATABASE" --schema-only --no-owner --no-privileges \
  --no-comments -n public | grep -Ev '^\\(un)?restrict ' | sed -e '/^-- Dumped \(from\|by\)/d'
