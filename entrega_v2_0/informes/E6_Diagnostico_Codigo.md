# Entregable 6 — Diagnóstico del código Python y del modelo MILP (v1.4.0)

**Alcance:** `Optimizacion_MILP_SAGAPI.py` (413 líneas), los 22 módulos de `sagapi/` (≈ 3 900 líneas), `herramientas/` y `tests/` (50 pruebas + enumeración). En esta etapa **no se modificó el código**. Las cifras provienen de ejecuciones reales guardadas en `entrega_v2_0/verificacion/`:

- `verificacion_bd_v2.json`: pruebas y corridas comparadas.
- `evidencia_diagnostico_codigo.json`: experimentos específicos de este diagnóstico.
- `anual_E1/`: corrida del comando `anual`.

**Clasificación usada:**

- **ERROR**: produce un resultado incorrecto o un efecto no declarado.
- **DEFECTO DE DISEÑO**: el código hace lo que dice, pero eso no representa lo que se pretende.
- **LIMITACIÓN**: supuesto declarado que restringe las conclusiones.
- **RIESGO**: fallará ante un cambio razonable.
- **CALIDAD**: mantenibilidad o reproducibilidad.

---

## 1. Lo que está bien (y debe preservarse)

- **Formulación R1–R10 correcta.** Comprobé algebraicamente las big-M de `modelo.py`:
  - R4–R5: `Mab = UB + p_a − lb_b` es la cota mínima válida para relajar `S_b ≥ S_a + p_a`.
  - R7–R8: `Mj = UB + max p − d_j`.
  - R9: `g ≥ aT − M·v`, `g ≥ tope·v`, al minimizar da `g = min(aT, tope)`, correcto.
  - R10: desviación con `dp − dm` correcta.
- **Validación por enumeración.** En 40/40 microinstancias aleatorias el MILP reproduce los óptimos lexicográficos f1, f1b y f2 obtenidos por enumeración exhaustiva y PL (`tests/test_enumeracion.py`). Ejecutado de nuevo en esta auditoría con la base original y con la v2.0: 40/40 en ambos casos.
- **Verificación independiente.** Hay dos niveles de comprobación ajenos al solucionador:
  - `solver.validar_vector` comprueba cada fila Ax ∈ [lo, hi], las cotas y la integralidad.
  - `verificacion.verificar` comprueba la factibilidad física: precedencia, no solape, ventanas y liberación.
- **Honestidad del estado.** Solo se declara ÓPTIMO cuando HiGHS cierra la brecha en todas las fases (`optimizacion._estado`). Se eliminó la "votación entre configuraciones" de versiones anteriores, y la heurística de respaldo nunca se certifica.
- **API pública de SciPy (`scipy.optimize.milp`)**, sin dependencias comerciales; exportación MPS estándar.
- **Separación instancia / estado / modelo / solver** razonable. El concepto predictivo-reactivo (O^C, O^E, O^I, O^P) está bien implementado en `estado.particionar`.

---

## 2. Hallazgos

### 2.1 Modelo matemático

| ID | Tipo | Hallazgo | Evidencia |
|---|---|---|---|
| **C-01** | DEFECTO DE DISEÑO | **R11 (personal en el modelo principal) no restringe la programación.** Crea `a_personal[m,w]` con "1 persona por máquina potencialmente usada" y "cada persona ≤ 1 máquina", pero **ninguna fila de R11 contiene variables S_o ni x_om**. Es una prueba de emparejamiento estática que vuelve infactible el problema si faltan habilidades y que, en otro caso, no influye en la solución. No modela tiempo, simultaneidad real ni operaciones que requieran 2 personas. | `modelo.py:153-172`. Experimento S06A: f1* = 9 066,34 con R11 (342 binarias) y **sin R11 (282 binarias)**: idéntico. Variables de programación en las filas de R11: **0**. |
| **C-02** | LIMITACIÓN | **El personal integrado real** (`personal_integrado.py`: q[o,w], disyunciones por trabajador R13, R14, R15) es correcto, pero solo se usa en el piloto, con un tope de 24–36 operaciones libres; el resto de la planta queda congelado como FIFO. | `personal_integrado.py:24-28`; rodante S08A = 23 operaciones comprometidas de 1 152 (2,0 %); S13A = 2 (0,17 %). |
| **C-03** | LIMITACIÓN | **Capacidad unitaria de todo recurso.** Las disyunciones R4–R5 se aplican por nombre de recurso; "Cantidad de escenario" solo se valida (≥ 1). Mesa de armado, área de inspección, zona de embalaje y preparación no admiten dos pedidos a la vez. | `modelo.py:76-100`; `datos.validar`. |
| **C-04** | ERROR (físico) | **Las operaciones POR_LOTE se parten entre jornadas.** El eje de horas productivas es continuo: un curado que empieza 20 min antes del cierre termina al día siguiente a las 08:xx. Un ciclo de horno no puede suspenderse. | 10 de 96 curados del FIFO cruzan el cierre (`evidencia_diagnostico_codigo.json`). |
| **C-05** | DEFECTO DE DISEÑO | **El objetivo lexicográfico con penalidad fija sacrifica la tardanza.** P1 minimiza el *número ponderado* de pedidos atrasados (P_j·U_j), así que un pedido que ya está tarde puede retrasarse sin costo en P1. En S06A, LEX baja de 7 a 4 atrasados, pero la tardanza ponderada **sube** de 205,6 a 249,2 h y el desplazamiento D sube de 35 a 2 031 h. La "penalidad del 10 %" es además un supuesto sin cláusula. | `caso S06A` (salidas idénticas con v1.2 y v2.0); `optimizacion.lexicografico`. |
| **C-06** | LIMITACIÓN | **Precedencia lineal con lote completo:** `S_b ≥ S_a + p_a`. No hay lotes de transferencia ni ramas paralelas (corte de planchas ∥ corte de tubos). Además, las disyunciones R4–R5 omiten los pares del mismo pedido porque la cadena lineal ya los separa: si se introducen rutas no lineales hay que añadir esos pares. | `modelo.py:65-72, 83-85`; 3 pedidos infactibles por construcción. |
| **C-07** | RIESGO | **Big-M de R6 sin activar x = 0.** Con x = 0 y z = 0 queda `S ≤ a − p + UB`; corta soluciones válidas si `a < p`. Hoy no ocurre (0 ventanas con a < p_max = 26,3 h), pero ocurriría con averías en la primera semana del horizonte. | `modelo.py:113`. |
| **C-08** | DEFECTO DE DISEÑO | **Miopía de `evento_unico` (E2, Monte Carlo, `caso`).** Solo entran los pedidos liberados en t_b; los pedidos que se liberan después no se modelan ni se miden. El MILP puede ocupar capacidad que el FIFO reservaba para ellos, sin costo en los indicadores. En S06A no hubo cruces (0), pero el diseño no lo impide (32 pedidos futuros ignorados). | `experimentos.py:47`; evidencia S06A. |
| **C-09** | LIMITACIÓN | **Horas fijas en el código.** Liberación a las 08:00 y vencimiento al cierre del día; los parámetros homónimos del Excel no se leen. | `instancia.py:50`; `calendario.fin_de_dia`. |
| **C-10** | CALIDAD (escala) | **El modelo monolítico es inviable:** 96 pedidos producen **55 248 variables, 54 000 binarias (52 560 pares disyuntivos) y 117 940 restricciones**. La descomposición por eventos es necesaria y correcta; el horizonte rodante con personal no escala más allá de unas 36 operaciones. | `ModeloMILP(subproblema_inicial(I))` (0,4 s en construirse; no se resolvió). |

### 2.2 Experimentos y conclusiones

| ID | Tipo | Hallazgo | Evidencia |
|---|---|---|---|
| **C-11** | DEFECTO DE DISEÑO | **El comparador FIFO es débil.** Sin averías: FIFO 73 atrasados, **EDD 27**, MILP 19. Con las 12 averías: 74 / 27 / 19. El 85 % de la mejora frente al FIFO (46 de 54 pedidos) también la logra una regla EDD; las averías apenas mueven los resultados. Las conclusiones deben compararse contra EDD y separar el efecto de secuenciación del de reprogramación. | `anual_E1/E1_anual.csv` (idéntico con v1.2 y v2.0). |
| **C-12** | DEFECTO DE DISEÑO | **Selección del piloto por índice.** Se eligen `candidatos[:N]`: los N primeros pedidos activos por orden de código, no los afectados por la falla. El sesgo de selección no está documentado. | `Optimizacion_MILP_SAGAPI.py:151, 303`. |
| **C-13** | LIMITACIÓN | **Wilcoxon sobre escenarios no independientes.** Comparten el mismo programa base, los mismos pedidos y la misma máquina, así que los valores p están sobrestimados en significancia. | `reportes.py:93-101, 154-164`. |
| **C-14** | LIMITACIÓN | **Monte Carlo circular:** remuestrea duraciones de 12 fallas sintéticas. No mide la fiabilidad real. | `experimentos.e5_montecarlo`. |
| **C-15** | ERROR | **Sensibilidad desconectada del Excel.** `27_SENSIBILIDAD` se lee, pero los niveles están fijos en el código (0,5–4; 0–24; 1,0–1,25). Cambiar el Excel no tiene efecto. | `experimentos.py:303-335`. |

### 2.3 Datos, entradas y salidas

| ID | Tipo | Hallazgo | Evidencia |
|---|---|---|---|
| **C-16** | RIESGO | **Lectura silenciosa de fórmulas.** `openpyxl` con `data_only=False` hace que `_num` devuelva el valor por defecto si la celda contiene "=…". Una entrada convertida en fórmula se ignora **sin aviso**; ya ocurre con el "Lote" de 08 en v1.2. | `datos.py:48-56, 110`. |
| **C-17** | RIESGO | **Esquema implícito y frágil.** Los encabezados exactos con unidades ("Costo de uso S//h") no se validan; en 06B cualquier columna extra se toma por máquina; 6 parámetros con nombre exacto caen silenciosamente a valores por defecto. | `datos.py:16-22, 186-194`; ver `4_DEPENDENCIAS_PYTHON`. |
| **C-18** | ERROR | **Feriados leídos de dos formas distintas.** `datos.leer` excluye "no", "-" y "0"; `e4_anual_sensibilidad` toma cualquier texto como feriado y reconstruye el calendario sin los tramos configurados. | `datos.py:124`; `experimentos.py:366-369`. |
| **C-19** | ERROR | **Los reportes sobrescriben la base de datos.** `reportes.escribir_excel` guarda en `E.archivo` (el Excel de entrada), borra imágenes (openpyxl), depende de que exista `24_VALIDACIONES` y busca `herramientas/img`, que no está en la entrega. | `reportes.py:394, 487-515`. |
| **C-20** | CALIDAD | **El generador de datos no reproduce la base.** `construir_base_final.py` crea 10 operarios con nombres y requiere archivos ausentes (V13, Data_SAGAPI_PIA). | Ver E-084. |

### 2.4 Arquitectura, calidad y reproducibilidad

| ID | Tipo | Hallazgo | Evidencia |
|---|---|---|---|
| **C-21** | CALIDAD | **Tres implementaciones del lexicográfico** con criterios distintos: `optimizacion.lexicografico` acepta incumbentes no certificados y respaldo heurístico; `rodante_personal.resolver_lex` aborta si una fase no está certificada; `cmd_integrar_personal.fase` añade filas permanentes. | `optimizacion.py:70`; `rodante_personal.py:51`; `Optimizacion_MILP_SAGAPI.py:177`. |
| **C-22** | CALIDAD | **Comandos extensos en el programa principal.** `cmd_integrar_personal` tiene unas 160 líneas de lógica de negocio. El estilo es heterogéneo (líneas comprimidas sin espacios en `rodante_personal`, `jornada_piloto`, `personal_integrado`) y la versión interna es inconsistente ("1.3.4-piloto-rodante-auditable" dentro de la 1.4.0). | `Optimizacion_MILP_SAGAPI.py:125-287`; `rodante_personal.py:247`. |
| **C-23** | CALIDAD | **Dependencias sin fijar** (`scipy>=1.13`). Se usan SciPy 1.18.1 y HiGHS sin control de hilos ni semilla, así que los tiempos y, en empates, la solución elegida pueden variar entre equipos. | `requirements.txt`; `solver.py` (docstring). |
| **C-24** | CALIDAD | **Las pruebas no cubren el riesgo principal.** No hay pruebas de esquema del Excel, calendario con feriados, capacidad > 1, horno partido, R6 con a < p ni R11 inerte. Las pruebas de regresión fijan números de datos sintéticos (`P071`, 32 operaciones), así que fallarán con datos reales sin que haya un error. | `tests/`. |
| **C-25** | CALIDAD | **Indicadores incompletos.** Falta la utilización por recurso en el programa resultante y la carga por persona. La "participación humana" solo se mide como conflictos de emparejamiento. | `indicadores.py`, `verificacion.control_personal`. |

---

## 3. Correspondencia entre el modelo declarado y el código

| Elemento declarado (docstrings, Cap. 3) | Implementado | Observación |
|---|---|---|
| Variables S, x, y, z, T, U, g, v, dp, dm | Sí | Coinciden. |
| Objetivo lexicográfico P1 → P2 → P3 | Sí, en tres variantes | C-21. |
| ε-restricción aumentada | Sí (`optimizacion.epsilon`) | ρ·f1b/rango; el frente es aproximado (7 niveles). |
| "Restricciones de asignación de trabajadores" (texto para la memoria) | **Solo R11 estática** en el modelo general; integración real solo en el piloto | C-01/C-02. El texto de la memoria debe precisarlo. |
| Jornada de 8 h por trabajador | Comprobación **a posteriori** (`jornada_piloto`), no restricción | Coherente con un solo turno, pero no se modela. |
| Disponibilidad por jornada | Eje de horas productivas | C-04 (horno partido). |
| Averías y recuperación A/B | Sí (`estado.tiempo_restante`) | Correcto para POR_UNIDAD; POR_LOTE siempre reinicia. |
| Horizonte rodante | Piloto (N pedidos, compromiso por turno) | C-02, C-12. |

---

## 4. Factibilidad matemática frente a factibilidad en planta

Que una solución sea factible para el MILP **no** implica que sea ejecutable en planta, por cinco razones:

1. Los tiempos no están medidos.
2. Las habilidades son simuladas y, en el modelo general, R11 no las vincula al horario.
3. El horno puede quedar partido entre jornadas.
4. Los puestos manuales tienen capacidad 1.
5. Las operaciones de pedidos futuros o externos están congeladas en un FIFO que no se reoptimiza.

Las auditorías "sin errores" de los pilotos garantizan la coherencia interna del conjunto exportado, como el propio código declara.

## 5. Rendimiento observado

| Ejecución | Tiempo |
|---|---|
| `validar` | 1,9–3,3 s |
| 50 pruebas unitarias | 1,3–2,1 s |
| Enumeración de 40 microinstancias | 5 s |
| Rodante S08A, 5 ventanas | 2,0–2,7 s |
| `caso S06A` (4 métodos) | 10–11 s |
| `anual` completo (8 combinaciones) | 62 s; 96 decisiones MILP, todas ÓPTIMO; máximo 358 binarias |

La validación con el libro MODELO v2.0 tardó 1,9 s frente a 3,3 s con el v1.2 (libro más pequeño, sin hojas de resultados ni imágenes). El rendimiento **no** es hoy el cuello de botella; sí lo será cuando se intente integrar el personal a escala anual (C-10).
