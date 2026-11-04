# ManejadorFinanzas · Mi plan

Aplicación de escritorio para gestionar deudas, metas de ahorro, movimientos y presupuesto personal. Construida con **Python 3.12+, Qt/PySide6, SQLAlchemy y SQLite**. Funciona en una ventana nativa de Windows, sin navegador ni servidor web.

## Funciones

- Resumen de saldos, progreso y capacidad de pago quincenal.
- Creación y edición de deudas y metas, abonos, aportes e historial de movimientos.
- Presupuesto mensual o quincenal con gastos fijos, variables y reserva.
- Distribución de una capacidad compartida entre objetivos, sin asignar el mismo ingreso varias veces.
- Simulaciones de plazos y aportes que no modifican los registros reales.
- Revisión de observaciones de gastos desde una instantánea local compatible con alertas bancarias.

El módulo de gastos trabaja con una ventana de fechas de demostración de 2026. No se conecta a Gmail ni sincroniza correos. La evidencia personal no forma parte del repositorio. Los cálculos del plan no incluyen intereses ni ejecutan pagos.

## Instalación y ejecución

Desde la carpeta del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Después de instalar las dependencias, también puedes abrir **iniciar.bat**. El lanzador utiliza el entorno virtual; todavía no es un ejecutable independiente para equipos sin Python.

Los importes se ingresan sin separadores de miles, por ejemplo `4000000` o `4000000.50`, y se muestran en pesos colombianos (COP).

## Datos locales y configuración

La aplicación crea `data/finanzas.db` al iniciar. La carpeta `data/`, las bases de datos, las credenciales y las capturas locales están excluidas de Git. El código publicado incluye ejemplos ficticios; cada persona puede editar o eliminar los registros desde la interfaz. Los ejemplos se cargan una sola vez.

Para cambiar la ruta de la base, define `FINANZAS_DB_PATH` antes de iniciar. Para respaldarla, cierra la aplicación y copia `data/`. No borres esta carpeta al actualizar el código.

La configuración personal opcional se guarda en `data/local_config.json`. Puedes copiar [config/local_config.example.json](config/local_config.example.json) a esa ruta y ajustar:

- `seed_examples`: lista de ejemplos iniciales con nombre, tipo (`debt` o `goal`), total y aporte inicial, usando importes como cadenas. Solo se utiliza cuando todavía no se han cargado ejemplos.
- `own_transfer_pattern`: expresión regular para reconocer destinatarios propios en la evidencia bancaria. Usa únicamente identificadores tuyos y conserva el archivo fuera de Git.

Si no existe esta configuración, se utilizan ejemplos y destinatarios ficticios. No se incluyen datos financieros reales ni correos privados. El script de una revisión financiera personal previa permanece solo en la copia local y está excluido de Git.

## Reglas de cálculo

Los importes se calculan con `Decimal` y se almacenan en centavos enteros. Los saldos y el progreso se derivan del historial; las escrituras usan transacciones para impedir sobrepagos concurrentes.

```text
capacidad quincenal = máximo(0, ingreso neto mensual − fijos − variables − reserva) / 2
```

Se consideran dos quincenas por mes. Los gastos y la reserva se registran mensualmente; un ingreso quincenal se convierte a mensual. Los gastos fijos pueden desglosarse con frecuencia mensual o semanal. El cálculo evita duplicar los cargos recurrentes al aplicar una base de gastos.

Las estimaciones suponen ingresos y gastos constantes y un escenario sin intereses. Los objetivos excluidos del plan no consumen capacidad compartida. Un déficit se muestra por separado.

## Estructura

```text
app.py                         Punto de entrada
iniciar.bat                    Lanzador para Windows
config/                        Rutas, fecha y configuración de ejemplo
desktop/                       Ventanas, formularios y componentes Qt
services/                      Presupuesto, cálculos, metas y gastos
database/                      Modelos y transacciones SQLite
repositories/                  Consultas de persistencia
utils/                         Formato y validación de importes
tests/                         Pruebas con datos ficticios y bases temporales
scripts/preview_desktop.py      Capturas locales sin ventanas visibles
```

## Verificación

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas usan bases temporales y Qt en modo sin pantalla. Cubren precisión de importes, pagos, persistencia, concurrencia, presupuesto, distribución compartida, revisión de gastos y navegación. Los tests aíslan la configuración privada de la máquina.

Para generar capturas locales:

```powershell
.\.venv\Scripts\python.exe scripts/preview_desktop.py
```

Las capturas se guardan bajo `data/` y no se publican.
