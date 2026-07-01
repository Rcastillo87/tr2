<?php

namespace App\Exports;

use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;
use PhpOffice\PhpSpreadsheet\Style\Fill;
use PhpOffice\PhpSpreadsheet\Style\Border;
use Symfony\Component\HttpFoundation\StreamedResponse;

class BacktestMonthlyExport
{
    private const HEADER_FILL = '1E2530';

    /**
     * Genera y descarga un archivo Excel con 3 hojas:
     * Resumen, Parametros completos, Mes a mes.
     */
    public static function download(array $result, string $filename): StreamedResponse
    {
        $spreadsheet = new Spreadsheet();

        self::buildSummarySheet($spreadsheet, $result);
        self::buildParamsSheet($spreadsheet, $result);
        self::buildMonthlySheet($spreadsheet, $result);

        $spreadsheet->setActiveSheetIndex(0);
        $writer = new Xlsx($spreadsheet);

        return new StreamedResponse(function () use ($writer) {
            $writer->save('php://output');
        }, 200, [
            'Content-Type'        => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'Content-Disposition' => "attachment; filename=\"{$filename}\"",
            'Cache-Control'       => 'max-age=0',
        ]);
    }

    private static function headerRow($sheet, string $range): void
    {
        $sheet->getStyle($range)->getFont()->setBold(true);
        $sheet->getStyle($range)->getFill()
            ->setFillType(Fill::FILL_SOLID)->getStartColor()->setRGB(self::HEADER_FILL);
        $sheet->getStyle($range)->getFont()->getColor()->setRGB('FFFFFF');
    }

    private static function buildSummarySheet(Spreadsheet $spreadsheet, array $result): void
    {
        $sheet  = $spreadsheet->getActiveSheet();
        $sheet->setTitle('Resumen');

        $agg     = $result['aggregate_metrics'] ?? [];
        $monthly = $result['monthly_breakdown'] ?? [];

        // Calcular métricas adicionales del monthly_breakdown
        $monthlyPnls   = collect($monthly)->pluck('total_pnl_pct')->map(fn($v) => (float)$v);
        $auditedMonths = $monthlyPnls->count();
        $avgMonthlyPnl = $auditedMonths > 0 ? round($monthlyPnls->average(), 2) : null;
        $bestMonth     = $auditedMonths > 0 ? round($monthlyPnls->max(), 2) : null;
        $worstMonth    = $auditedMonths > 0 ? round($monthlyPnls->min(), 2) : null;
        $totalReturnPct = $auditedMonths > 0 ? round($monthlyPnls->sum(), 2) : null;
        $avgWinRate    = $auditedMonths > 0
            ? round(collect($monthly)->pluck('win_rate')->map(fn($v) => (float)$v)->average(), 2)
            : null;

        $sheet->setCellValue('A1', 'Backtest — Resumen');
        $sheet->getStyle('A1')->getFont()->setBold(true)->setSize(14);

        $sheet->setCellValue('A3', 'Estrategia');
        $sheet->setCellValue('B3', $result['strategy'] ?? '—');
        $sheet->setCellValue('A4', 'Símbolo');
        $sheet->setCellValue('B4', $result['symbol'] ?? '—');
        $sheet->setCellValue('A5', 'Intervalo');
        $sheet->setCellValue('B5', $result['interval'] ?? '—');
        $sheet->setCellValue('A6', 'Fecha de ejecución');
        $sheet->setCellValue('B6', now()->format('Y-m-d H:i:s'));
        $sheet->setCellValue('A7', 'Aprobada');
        $sheet->setCellValue('B7', ($result['passed'] ?? false) ? 'Sí' : 'No');

        $rows = [
            ['Total trades',            $agg['total_trades'] ?? 0],
            ['Win rate (%)',             $agg['win_rate'] ?? 0],
            ['Sharpe ratio',             $agg['sharpe_ratio'] ?? 0],
            ['Meses testeados',          $auditedMonths],
            ['Win rate prom./mes (%)',   $avgWinRate ?? '—'],
            ['Retorno prom./mes (%)',    $avgMonthlyPnl ?? '—'],
            ['Retorno total (%)',        $totalReturnPct ?? '—'],
            ['Mejor mes (%)',            $bestMonth ?? '—'],
            ['Peor mes (%)',             $worstMonth ?? '—'],
            ['Avg win (%)',              $agg['avg_win_pct'] ?? 0],
            ['Avg loss (%)',             $agg['avg_loss_pct'] ?? 0],
            ['Max drawdown (%)',         $agg['max_drawdown_pct'] ?? 0],
        ];

        $row = 9;
        $sheet->setCellValue("A{$row}", 'Métrica');
        $sheet->setCellValue("B{$row}", 'Valor');
        self::headerRow($sheet, "A{$row}:B{$row}");

        foreach ($rows as $r) {
            $row++;
            $sheet->setCellValue("A{$row}", $r[0]);
            $sheet->setCellValue("B{$row}", $r[1]);

            // Colorear métricas de retorno
            if (in_array($r[0], ['Retorno prom./mes (%)', 'Retorno total (%)', 'Mejor mes (%)', 'Peor mes (%)'])) {
                $val   = is_numeric($r[1]) ? $r[1] : 0;
                $color = $val >= 0 ? '3DD68C' : 'F2545B';
                $sheet->getStyle("B{$row}")->getFont()->getColor()->setRGB($color);
            }
        }

        if (!empty($result['pass_reasons'])) {
            $row += 2;
            $sheet->setCellValue("A{$row}", 'Criterios de evaluación');
            $sheet->getStyle("A{$row}")->getFont()->setBold(true);
            foreach ($result['pass_reasons'] as $reason) {
                $row++;
                $sheet->setCellValue("A{$row}", '• ' . $reason);
            }
        }

        $sheet->getColumnDimension('A')->setWidth(26);
        $sheet->getColumnDimension('B')->setWidth(40);
    }

    private static function buildParamsSheet(Spreadsheet $spreadsheet, array $result): void
    {
        $sheet  = $spreadsheet->createSheet();
        $sheet->setTitle('Parámetros completos');

        $params = $result['_implement_params'] ?? [];

        $sheet->setCellValue('A1', 'Parámetro');
        $sheet->setCellValue('B1', 'Valor');
        self::headerRow($sheet, 'A1:B1');

        $labels = [
            'sl_pct'                     => 'Stop Loss %',
            'tp_pct'                     => 'Take Profit 1 %',
            'tp2_pct'                    => 'Take Profit 2 %',
            'tp3_pct'                    => 'Take Profit 3 %',
            'tp4_pct'                    => 'Take Profit 4 %',
            'be_pct'                     => 'Break-even %',
            'max_duration'               => 'Máx. duración (velas)',
            'risk_per_trade_pct'         => 'Riesgo por trade %',
            'regime_filter'              => 'Filtro de régimen',
            'macro_trend_filter'         => 'Filtro de tendencia macro H4',
            'mode'                       => 'Modo (VWAP)',
            'trailing_mode'              => 'Modo de trailing stop',
            'trailing_distance_pct'      => 'Distancia trailing %',
            'trailing_steps'             => 'Escalones de trailing',
            'volatility_protection_mode' => 'Protección por volatilidad',
            'volatility_atr_multiplier'  => 'Multiplicador ATR',
            'volatility_widen_pct'       => 'Ampliación SL volatilidad %',
            'start_date'                 => 'Fecha desde',
            'end_date'                   => 'Fecha hasta',
        ];

        $row = 1;
        foreach ($labels as $key => $label) {
            if (!array_key_exists($key, $params) || $params[$key] === null || $params[$key] === '') {
                continue;
            }
            $row++;
            $value = $params[$key];
            if (is_bool($value))   $value = $value ? 'Sí' : 'No';
            if (is_array($value))  $value = json_encode($value);
            $sheet->setCellValue("A{$row}", $label);
            $sheet->setCellValue("B{$row}", $value);
        }

        if (!isset($params['start_date']) && !isset($params['end_date'])) {
            $row++;
            $sheet->setCellValue("A{$row}", 'Rango de fechas');
            $sheet->setCellValue("B{$row}", 'Histórico completo disponible');
        }

        $sheet->getColumnDimension('A')->setWidth(30);
        $sheet->getColumnDimension('B')->setWidth(30);
        $sheet->getStyle("A1:B{$row}")->getBorders()->getAllBorders()
            ->setBorderStyle(Border::BORDER_THIN)->getColor()->setRGB('CCCCCC');
    }

    private static function buildMonthlySheet(Spreadsheet $spreadsheet, array $result): void
    {
        $sheet = $spreadsheet->createSheet();
        $sheet->setTitle('Mes a mes');

        // Sin columna P&L USDT
        $headers = ['Mes', 'Trades', 'Ganadores', 'Perdedores', 'Win rate (%)', 'P&L (%)'];
        $col = 'A';
        foreach ($headers as $h) {
            $sheet->setCellValue("{$col}1", $h);
            $col++;
        }
        self::headerRow($sheet, 'A1:F1');

        $breakdown = $result['monthly_breakdown'] ?? [];
        $row = 2;

        foreach ($breakdown as $m) {
            $sheet->setCellValue("A{$row}", $m['month']);
            $sheet->setCellValue("B{$row}", $m['total_trades']);
            $sheet->setCellValue("C{$row}", $m['wins']);
            $sheet->setCellValue("D{$row}", $m['losses']);
            $sheet->setCellValue("E{$row}", $m['win_rate']);
            $sheet->setCellValue("F{$row}", $m['total_pnl_pct']);

            $color = $m['total_pnl_pct'] >= 0 ? '3DD68C' : 'F2545B';
            $sheet->getStyle("F{$row}")->getFont()->getColor()->setRGB($color);
            $row++;
        }

        // Fila de totales/promedios
        if ($row > 2) {
            $sheet->setCellValue("A{$row}", 'PROMEDIO');
            $sheet->getStyle("A{$row}")->getFont()->setBold(true);
            $sheet->setCellValue("B{$row}", "=AVERAGE(B2:B" . ($row-1) . ")");
            $sheet->setCellValue("E{$row}", "=AVERAGE(E2:E" . ($row-1) . ")");
            $sheet->setCellValue("F{$row}", "=AVERAGE(F2:F" . ($row-1) . ")");
            $sheet->getStyle("A{$row}:F{$row}")->getFont()->setBold(true);
            $row++;
            $sheet->setCellValue("A{$row}", 'TOTAL P&L %');
            $sheet->getStyle("A{$row}")->getFont()->setBold(true);
            $sheet->setCellValue("F{$row}", "=SUM(F2:F" . ($row-2) . ")");
            $sheet->getStyle("A{$row}:F{$row}")->getFont()->setBold(true);
        }

        foreach (range('A', 'F') as $c) {
            $sheet->getColumnDimension($c)->setAutoSize(true);
        }

        $sheet->getStyle("A1:F" . ($row))->getBorders()->getAllBorders()
            ->setBorderStyle(Border::BORDER_THIN)->getColor()->setRGB('CCCCCC');
    }
}
