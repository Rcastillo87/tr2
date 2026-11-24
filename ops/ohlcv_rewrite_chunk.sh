#!/bin/bash
# C6-05 (parte 2): reescribe fragmentos de ohlcv_data con lotes comprimidos solapados (los que avisa
# `php artisan ohlcv:overlap-check`). Por cada fragmento: 1) respaldo de todas sus velas (csv.gz); 2) decompress_chunk +
# compress_chunk en UNA transacción (database/sql/ohlcv_rewrite_chunk.sql) que solo se confirma si las velas quedan
# idénticas al respaldo (número y md5); si no, se deshace sola. No cambia ninguna vela: solo cómo están guardadas.
# Uso (root, sin búsquedas en curso y lejos de la compresión automática 05:38 / 17:38 UTC):
#   bash ops/ohlcv_rewrite_chunk.sh _hyper_1_123_chunk [_hyper_1_124_chunk …]
# Respaldo: /root/patches/ohlcv_rewrite/<fragmento>_<fecha>.csv.gz (se conserva).
set -euo pipefail
R=$(cd "$(dirname "$0")/.." && pwd)
SQL="$R/database/sql/ohlcv_rewrite_chunk.sql"
PG=${TR2_PG:-"runuser -u postgres -- psql -X -q -d trading2"}
OUT=${TR2_OHLCV_BACKUP:-/root/patches/ohlcv_rewrite}
say(){ echo "[ohlcv-rewrite] $*"; }
die(){ say "ABORTADO: $*"; exit 1; }
[ $# -ge 1 ] || die "uso: bash ops/ohlcv_rewrite_chunk.sh <fragmento> [...]"
[ -f "$SQL" ] || die "no está $SQL"
mkdir -p "$OUT"; chmod 700 "$OUT"
cd /   # postgres no puede entrar a la carpeta del proyecto
for c in "$@"; do
  [[ $c =~ ^_hyper_[0-9]+_[0-9]+_chunk$ ]] || die "nombre de fragmento inválido: $c"
  q=$($PG -tA -v ON_ERROR_STOP=1 -c "SELECT c.schema_name || '.' || c.table_name FROM _timescaledb_catalog.chunk c
        JOIN _timescaledb_catalog.hypertable h ON h.id = c.hypertable_id
        WHERE h.table_name = 'ohlcv_data' AND c.table_name = '$c' AND c.compressed_chunk_id IS NOT NULL") \
    || die "no se pudo consultar el catálogo de TimescaleDB"
  [ -n "$q" ] || die "$c no es un fragmento comprimido de ohlcv_data (nada que reescribir)"
  f="$OUT/${c}_$(date -u +%Y%m%dT%H%M%SZ).csv.gz"
  $PG -v ON_ERROR_STOP=1 -c "COPY (SELECT * FROM $q) TO STDOUT WITH (FORMAT csv, HEADER)" | gzip > "$f" \
    || die "$c: el respaldo falló (no se tocó nada)"
  gzip -t "$f" || die "$c: el respaldo $f está dañado (no se tocó nada)"
  rows=$(gunzip -c "$f" | tail -n +2 | wc -l)
  [ "$rows" -gt 0 ] || die "$c: respaldo vacío (no se tocó nada)"
  say "$c: respaldo de $rows velas en $f"
  t0=$(date +%s)
  if ! out=$($PG -v ON_ERROR_STOP=1 -v chunk="$q" -v rows="$rows" < "$SQL" 2>&1); then
    echo "$out" | grep -E "ERROR" | tail -3
    die "$c: no se reescribió; la transacción se deshizo y las velas quedan como estaban (respaldo en $f)"
  fi
  echo "$out" | grep -q "IDENTICAS $rows velas" || die "$c: no se vio la verificación final (revisar a mano; respaldo en $f)"
  say "$c: reescrito en $(( $(date +%s) - t0 )) s · $rows velas idénticas antes y después"
done
say "TERMINADO"
