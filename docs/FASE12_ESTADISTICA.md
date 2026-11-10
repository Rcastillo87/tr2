# Fase 12 — Validez estadística de los resultados (opciones para decidir)

> 2026-11-06 (Bogotá). Auditoría del 05-nov: NUEVO-04, NUEVO-05 y «otros riesgos estadísticos». **No son defectos de
> código: son decisiones de diseño.** Cada una cambia los resultados de búsquedas y backtests, por eso nada se programa
> sin la elección del dueño. Orden recomendado al final.

## 1. Holdout independiente (NUEVO-04)

**Hoy** (`cli/param_search.py`): el rango se parte en 2/3 + 1/3. Una configuración «sobrevive» si gana en los primeros
2/3 **y** en el último 1/3. Ese último tercio, aunque no se usa para ordenar, **sí decide qué se acepta**: con cientos
de configuraciones probadas, alguna pasa el filtro por suerte (sesgo de selección múltiple). No es un holdout limpio.

| Opción | Qué hace | Costo | Efecto |
|---|---|---|---|
| **A. Tres tramos** (recomendada) | 60 % elegir · 20 % aceptar (el filtro de hoy) · 20 % **solo informar**, nunca filtra. La pantalla muestra el resultado del último tramo como «fuera de muestra real». | Bajo: cambia el corte y agrega un bloque de métricas. | Menos datos para elegir (60 % en vez de 66 %). El número del último tramo es honesto. |
| B. Holdout temporal fijo | Los últimos N meses se reservan y no los ve **ninguna** búsqueda hasta una fecha que decide el dueño. | Bajo. Disciplina: no «mirar» antes de tiempo. | El más limpio, pero gasta datos recientes, que son los más parecidos al mercado actual. |
| C. Dejarlo y documentar | Rotular el último tercio como «validación» (no «fuera de muestra»). | Ninguno. | No resuelve el sesgo; solo lo nombra. |

> **Hecho aparte [p43, N-03, decisión del dueño 10-nov]:** el corte dejaba pasar dos contaminaciones que la opción
> elegida aquí necesitará de todas formas: (1) un trade que abría antes del corte y cerraba después contaba entero en el
> tramo de elección, con precios posteriores al corte; ahora no cuenta en ninguno y se informa como `cross`; (2) la
> simulación es continua y el PnL del último tramo venía escalado por el saldo ganado antes; ahora cada tramo se mide
> con `pnl_pct × INITIAL`. El sesgo de selección múltiple de esta sección sigue pendiente (opciones A–C).

## 2. Cartera con capital compartido (NUEVO-05)

**Hoy**: cada moneda se backtestea por separado con su propio saldo y los resultados se suman. No hay capital
compartido, ni límite de posiciones simultáneas, ni exposición total, ni correlación (las cripto suelen caer juntas).

| Opción | Qué hace | Costo | Efecto |
|---|---|---|---|
| **A. Simulador de cartera sobre los trades ya calculados** (recomendada) | Toma los trades de cada moneda (sin recalcular señales), los ordena en el tiempo y los ejecuta con **un saldo**, un tope de posiciones abiertas y de exposición total (configurables), y el riesgo por operación sobre el saldo común. Informa drawdown, exposición máxima y trades descartados por tope. | Medio: módulo nuevo en Python + una sección en la pantalla de resultados. | Resultado realista de «operar todas juntas». Rápido (no vuelve a simular velas). |
| B. Motor multi-moneda completo | Un solo motor recorre todas las monedas vela a vela. | Alto. | Máxima fidelidad (los descartes cambian las señales siguientes), pero es una reescritura del motor. |
| C. Solo advertir | Leyenda «no representa una cartera» en la pantalla. | Ninguno. | No da el número que importa. |

## 3. Walk forward con recalibración

**Hoy** (`window_stats`): una sola corrida continua se corta en 5 ventanas y se miden por separado. Mide
**estabilidad**, pero los parámetros son los mismos en todas las ventanas: no es un walk forward.

| Opción | Qué hace | Costo | Efecto |
|---|---|---|---|
| **A. Renombrar y mantener** (recomendada ahora) | La pantalla lo llama «estabilidad por tramos» (lo que es). | Ninguno. | Honesto. El walk forward real queda para cuando haya 1 y 2. |
| B. Walk forward real | Por cada ventana: búsqueda en el tramo anterior → prueba en la ventana → avanzar. | Alto: N búsquedas por corrida (horas). | Mide si el **método** de elegir parámetros funciona, no una configuración. |

## 4. Drawdown con riesgo flotante

**Hoy** (`metrics.py`): el drawdown se calcula con el saldo tras cada trade **cerrado**. Una posición que estuvo −8 %
y cerró en −1 % cuenta como −1 %.

| Opción | Qué hace | Costo | Efecto |
|---|---|---|---|
| **A. Curva de capital por vela** (recomendada) | El motor ya recorre cada vela: registra el saldo + PnL flotante (al cierre de cada vela, y el peor punto de la vela con su high/low). Se informan los dos: drawdown cerrado (el de hoy) y **drawdown flotante**. | Bajo/medio: el motor guarda un arreglo; las métricas agregan un campo. Sin costo notable en la búsqueda si solo se calcula el máximo. | El drawdown sube (es el real). Ningún otro resultado cambia. |
| B. Dejarlo | — | — | Subestima el riesgo. |

## 5. Tamaño de posición con costos

**Hoy** (`engine._position_size`): `tamaño = saldo × riesgo % / |entrada − SL|`. Si el SL salta, la pérdida real es
mayor que el riesgo % por comisión de entrada y salida y por slippage de salida (≈ 0,16 % del nocional con los valores
de hoy: 0,055 % × 2 + 0,05 %). Con SL de 1 % eso es ~16 % más pérdida de la prevista.

| Opción | Qué hace | Costo | Efecto |
|---|---|---|---|
| **A. Incluir costos en la distancia** (recomendada) | `distancia = |entrada − SL| + entrada × (2 × comisión + slippage)`. **En los tres motores a la vez** (backtest, Paper, Real) para no romper la paridad. | Bajo en código; **toca Real** (tamaño de las órdenes). | Posiciones algo más chicas; la pérdida en SL ≈ el riesgo % configurado. Todas las métricas cambian un poco. |
| B. Dejarlo y documentar | — | — | El riesgo efectivo es mayor que el configurado. |

## Recomendación de orden

1. **4A (drawdown flotante)**: no cambia ningún otro número y da la medida de riesgo correcta. Bajo riesgo.
2. **1A (tres tramos)**: hace honesto el número que más se usa para decidir.
3. **5A (costos en el tamaño)**: toca Real, en un parche propio, con la paridad de los tres motores probada.
4. **2A (cartera)**: el más útil para decidir cuánto capital poner, pero el más grande.
5. **3A ahora** (renombrar); 3B cuando 1 y 2 estén hechos.

Las búsquedas y backtests guardados **no se recalculan** solos: quedan con la versión con la que se corrieron
(se puede marcar en la pantalla qué versión de métricas tiene cada uno).
