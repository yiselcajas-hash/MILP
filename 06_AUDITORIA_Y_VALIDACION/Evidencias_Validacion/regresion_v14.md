# Regresión v2.0 frente a v1.4.0

**Objetivo.** Demostrar que los cambios de v2.0 no alteran lo que no debían alterar. Con la configuración de v1.4 (`regla_continuidad = NINGUNA`, es decir sin R12, y `regla_objetivo = PENALIDAD_FIJA`), v2.0 debe reproducir los resultados de v1.4 sobre la misma base de datos.

**Referencia.** Corridas de v1.4.0, sin modificaciones, sobre la base v2.0 compatible (etapa 1): `etapa1_auditoria/verificacion/anual_E1/E1_anual.csv` y `etapa1_auditoria/verificacion/logs/modelo_v2_0_caso_S06A.txt`.

## Caso S06A (avería F06 de la plegadora; 8 pedidos y 73 operaciones libres)

| Método | v1.4.0 | v2.0 con configuración v1.4 | Prueba |
|---|---|---|---|
| CONV | 7/8 atrasados · S/ 14 834 · Σw·T 205,6 | 7/8 · S/ 14 834 · 205,55 | `test_regresion_v14.py::test_caso_S06A` |
| EDD | 6/8 · S/ 15 299 · 196,6 | 6/8 · S/ 15 299 · 196,60 | ídem |
| MILP lexicográfico | 4/8 · S/ 9 066 · 249,2 · ÓPTIMO | 4/8 · S/ 9 066,34 · 249,18 · OPTIMO | ídem |

## Año 2025 por eventos (horizonte rodante)

| Escenario · combinación | v1.4.0 (atrasados · penalidad) | v2.0 con configuración v1.4 | ¿Coincide? |
|---|---|---|---|
| S00 · FIFO+CONV | 73 · 127 293,85 | 73 · 127 293,85 | Sí (prueba automática) |
| S00 · EDD+EDD | 27 · 83 231,19 | 27 · 83 231,19 | Sí (prueba automática) |
| S00 · MILP+CONV | 19 · 41 519,81 | 19 · 41 519,81 | Sí |
| S20A · FIFO+CONV | 74 · 130 474,44 | 74 · 130 474,44 | Sí (prueba automática) |
| S20A · FIFO+MILP | 55 · 94 970 | 55 · 94 970 | Sí |
| S20A · EDD+EDD | 27 · 84 065 | 27 · 84 065 | Sí |
| S20A · MILP+CONV | 23 · 47 727 | 22 · 46 221 | **No** (ver abajo) |
| S20A · MILP+MILP | 19 · 41 520 | 19 · 41 520 | Sí |

**Diferencia S20A · MILP+CONV (hallazgo N-05).**

* Todos los eventos MILP de ambas versiones terminaron con óptimo demostrado.
* En un horizonte rodante, cada evento puede tener varios programas óptimos con el mismo valor de P1 y P2. El programa elegido en un evento cambia el estado de partida de los eventos siguientes.
* Hay dos cambios de v2.0 que pueden cambiar cuál de esos óptimos alternativos devuelve HiGHS, sin cambiar el valor óptimo de ningún subproblema:
  * el big-M corregido de R6 (las filas son numéricamente distintas);
  * la ausencia de las filas R11.
* No se encontró ningún error que explique la diferencia. Se deja documentada como «No verificable» porque no es posible atribuirla a una causa única. El valor de v2.0 (22 atrasados) es mejor que el de v1.4 (23), lo que es coherente con una divergencia de trayectoria y no con una restricción violada: el verificador independiente no encontró violaciones.

## Mismo subproblema, mismo valor óptimo (E5)

En los subproblemas de la primera avería de S06A, S13A, S19A y S08A, v1.4.0 (ejecutado con su propio código y su Excel v1.2) y v2.0 con la configuración equivalente obtienen exactamente los mismos valores de P1 y P2. v2.0 lo hace con entre 10 % y 21 % menos variables (no hay filas ni variables R11). Detalle en `04_RESULTADOS/Resultados_MILP/E5_rendimiento.csv`.
