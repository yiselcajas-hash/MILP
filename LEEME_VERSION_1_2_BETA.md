# SAGAPI MILP 1.2.0-beta — dotación de 25 personas

## Qué se conoce realmente

- **Confirmado por la empresa:** 25 trabajadores en producción; un turno de 8 horas; rotación y reasignación de personal entre áreas según carga de producción.
- **No verificado:** competencias de cada persona, plantilla por proceso, ausencias, horarios exactos, descansos individuales y número de operarios requerido por operación/máquina.
- **Simulado:** los perfiles OP-01...OP-25 y la matriz de habilitaciones. Estos perfiles **no identifican empleados reales**.
- **Supuesto del modelo:** una persona habilitada por máquina ocupada durante toda la operación, sin relevos; se usa una reserva de una persona por recurso potencial **durante cada subproblema**, que es una formulación conservadora (más restrictiva que la rotación intraturno real).

## Cambios sobre 1.1.0

1. Archivo de entrada predeterminado: `Base_Datos_SAGAPI_25_TRABAJADORES_SIMULADOS_v1_2.xlsx`, que incluye `06_OPERARIOS` con 25 perfiles, `06B_HABILIDADES` con 25 filas y la hoja `06C_SUPUESTOS_PERSONAL`.
2. Nueva restricción MILP **R11_PERSONAL**: para cada máquina que potencialmente se puede utilizar en un subproblema se reserva exactamente una persona habilitada; ninguna persona se reserva en dos máquinas. El emparejamiento puede cambiar entre decisiones del horizonte rodante.
3. `validar` ahora informa cobertura de dotación y la correspondencia de respaldo entre máquinas y personas simuladas.
4. `caso` verifica si hay conflictos laborales, y el CSV de escenarios registra dichos conflictos.
5. La salida Markdown de reportes se escribe explícitamente en UTF-8, para evitar el error `cp1252` en Windows.
6. Se añaden pruebas unitarias de la matriz simulada y de la restricción R11.

## Limitaciones que impiden cerrar aún la investigación

**NO es una asignación flexible intraturno por operación.** R11 reserva personas por máquina durante el subproblema completo, y por tanto puede restringir indebidamente combinaciones que serían posibles mediante rotación dentro de la jornada. El escenario de habilidades ha sido construido para permitir cubrir simultáneamente todas las 15 máquinas activas y, por construcción, no genera conflictos laborales si los demás supuestos se cumplen. Esto **NO demuestra** que las competencias reales alcancen ese nivel.

La alternativa completa debe formular asignaciones específicas de operario por operación o intervalo e incorporar restricciones de no solapamiento y descansos; exige verificar el costo computacional y la matriz real de competencias. Hasta entonces, presentar los resultados exclusivamente como **simulación metodológica condicionada a los supuestos**.

La formulación no cambia la regla de penalidad supuesta del 10%, los pedidos sintéticos ni los eventos de falla simulados. No se han recalculado los experimentos completos E1-E5; los informes anteriores siguen siendo de 1.1.0 y **no deben confundirse con resultados de 1.2.0-beta**.

## Primeros pasos en Windows (carpeta nueva, sin reemplazar 1.1.0)

Desde la carpeta descomprimida `SAGAPI_MILP_v1_2_BETA`:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe Optimizacion_MILP_SAGAPI.py validar --salida resultados_v12
.venv\Scripts\python.exe Optimizacion_MILP_SAGAPI.py caso --escenario S08A --tl 60 --personal-estricto --salida resultados_v12
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tests.test_enumeracion 40
```

Para los reportes en Windows puede usarse el prefijo `-X utf8` si el entorno mantiene una configuración de consola heredada.

## Pruebas locales realizadas

- `validar`: 25 perfiles; 15 máquinas; 96 órdenes; 1152 operaciones; reproduce FIFO.
- `tests.test_solver_publico`: 4/4.
- `tests.test_personal_25`: 4/4.
- `tests.test_enumeracion 40`: f1 40/40, f1b 40/40, f2 40/40.
- Casos S08A y S13A con límites de 5 s por etapa: factibles/óptimos reportados por HiGHS, cero conflictos de personal en el escenario simulado. No sustituyen las pruebas E1-E5 completas.

**No sobrescribir los resultados anteriores**; use carpetas nuevas. La clasificación de origen de los datos está en `06C_SUPUESTOS_PERSONAL`.
