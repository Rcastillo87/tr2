<?php

namespace App\Exports;

use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;
use PhpOffice\PhpSpreadsheet\Style\Fill;
use PhpOffice\PhpSpreadsheet\Style\Border;
use Symfony\Component\HttpFoundation\StreamedResponse;

class BacktestMonthlyExport
{
    /**
     * Genera y descarga un archivo Excel con el resumen y el desglose mes a mes
     * de un resultado de backtest.
     */
    public static function download(array $result, string $filename): StreamedResponse
    {
        $spreadsheet = new Spreadsheet();

        self::buildSummarySheet($spreadsheet, $result);
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

    private static function buildSummarySheet(Spreadsheet $spreadsheet, array $result): void
    {
        $sheet = $spreadsheet->getActiveSheet();
        $sheet->setTitle('Resumen');

        $agg = $result['aggregate_metrics'] ?? [];

        $sheet->setCellValue('A1', 'Backtest — Resumen');
        $sheet->getStyle('A1')->getFont()->setBold(true)->setSize(14);

        $sheet->setCellValue('A3', 'Estrategia');
        $sheet->setCellValue('B3', $result['strategy'] ?? '—');
        $sheet->setCellValue('A4', 'Símbolo');
        $sheet->setCellValue('B4', $result['symbol'] ?? '—');
        $sheet->setCellValue('A5', 'Intervalo');
        $sheet->setCellValue('B5', $result['interval'] ?? '—');
        $sheet->setCellValue('A6', 'Aprobada');
        $sheet->setCellValue('B6', ($result['passed'] ?? false) ? 'Sí' : 'No');

        $rows = [
            ['Total trades',      $agg['total_trades'] ?? 0],
            ['Win rate (%)',      $agg['win_rate'] ?? 0],
            ['Profit factor',     $agg['profit_factor'] ?? '—'],
            ['Sharpe ratio',      $agg['sharpe_ratio'] ?? 0],
            ['Max drawdown (%)',  $agg['max_drawdown_pct'] ?? 0],
            ['Retorno total (%)', $agg['total_return_pct'] ?? 0],
            ['P&L total',         $agg['total_pnl'] ?? 0],
            ['Expectancy',        $agg['expectancy'] ?? 0],
        ];

        $row = 8;
        $sheet->setCellValue("A{$row}", 'Métrica');
        $sheet->setCellValue("B{$row}", 'Valor');
        $sheet->getStyle("A{$row}:B{$row}")->getFont()->setBold(true);
        $sheet->getStyle("A{$row}:B{$row}")->getFill()
            ->setFillType(Fill::FILL_SOLID)->getStartColor()->setRGB('1E2530');
        $sheet->getStyle("A{$row}:B{$row}")->getFont()->getColor()->setRGB('FFFFFF');

        foreach ($rows as $r) {
            $row++;
            $sheet->setCellValue("A{$row}", $r[0]);
            $sheet->setCellValue("B{$row}", $r[1]);
        }

        $sheet->getColumnDimension('A')->setWidth(22);
        $sheet->getColumnDimension('B')->setWidth(18);
    }

    private static function buildMonthlySheet(Spreadsheet $spreadsheet, array $result): void
    {
        $sheet = $spreadsheet->createSheet();
        $sheet->setTitle('Mes a mes');

        $headers = ['Mes', 'Trades', 'Ganadores', 'Perdedores', 'Win rate (%)', 'P&L (%)', 'P&L (USDT)'];
        $col = 'A';
        foreach ($headers as $h) {
            $sheet->setCellValue("{$col}1", $h);
            $col++;
        }
        $sheet->getStyle('A1:G1')->getFont()->setBold(true);
        $sheet->getStyle('A1:G1')->getFill()
            ->setFillType(Fill::FILL_SOLID)->getStartColor()->setRGB('1E2530');
        $sheet->getStyle('A1:G1')->getFont()->getColor()->setRGB('FFFFFF');

        $breakdown = $result['monthly_breakdown'] ?? [];
        $row = 2;

        foreach ($breakdown as $m) {
            $sheet->setCellValue("A{$row}", $m['month']);
            $sheet->setCellValue("B{$row}", $m['total_trades']);
            $sheet->setCellValue("C{$row}", $m['wins']);
            $sheet->setCellValue("D{$row}", $m['losses']);
            $sheet->setCellValue("E{$row}", $m['win_rate']);
            $sheet->setCellValue("F{$row}", $m['total_pnl_pct']);
            $sheet->setCellValue("G{$row}", $m['total_pnl']);

            // Colorear P&L: verde si positivo, rojo si negativo
            $pnlCell = "F{$row}";
            $color = $m['total_pnl_pct'] >= 0 ? '3DD68C' : 'F2545B';
            $sheet->getStyle($pnlCell)->getFont()->getColor()->setRGB($color);

            $row++;
        }

        foreach (range('A', 'G') as $c) {
            $sheet->getColumnDimension($c)->setAutoSize(true);
        }

        $sheet->getStyle("A1:G{$row}")->getBorders()->getAllBorders()
            ->setBorderStyle(Border::BORDER_THIN)->getColor()->setRGB('CCCCCC');
    }
}
