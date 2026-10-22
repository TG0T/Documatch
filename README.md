# Documatch

Documatch lee documentos tributarios chilenos y concilia **órdenes de compra**, **guías de despacho** y **facturas**.

Cada documento se sube como imagen o PDF. El sistema lo lee con OCR y reconoce su tipo, su número y las mercancías con sus cantidades. Después cruza los tres documentos para mostrar si lo pedido, lo despachado y lo facturado coinciden.

Proyecto Capstone (APT122) — DuocUC.

## Funcionalidades

- **Clasificación automática** de cada documento: factura, guía de despacho u orden de compra.
- **Número de documento** en formato `OC-123`, `G-123` o `F-123`.
- **Lectura de mercancías:**
  - lee cada ítem de la tabla del documento con su descripción y cantidad;
  - en facturas y órdenes de compra también lee el valor;
  - comprueba que la suma de los valores coincida con el neto impreso.
- **Dashboard de conciliación:**
  - una fila por orden de compra con sus guías y facturas;
  - avance del despacho y desglose de ítems;
  - estado de cada orden: *Conciliado*, *Despacho parcial*, *Discrepancia*, *Pendiente* o *Finalizada*.
- **Corrección de cantidades:** en una guía de despacho clasificada con menos de 65 % de confianza se pueden corregir a mano las cantidades leídas, desde el clasificador o desde el desglose del dashboard.
- **Sin duplicados:** no se acepta dos veces el mismo archivo ni dos documentos del mismo tipo con el mismo número (por ejemplo, dos `F-123`). La base de datos también lo impide.
- **Vinculación automática:** una guía o factura que menciona el número de su OC en las referencias se agrega sola a la fila de esa OC.
- **Cierre de despachos parciales:** una OC que recibió menos de lo pedido, y a la que solo se le facturó lo recibido, se puede dar por terminada indicando un motivo (por ejemplo, un acuerdo con el proveedor).
- **Datos de ejemplo** (dummies) para probar el dashboard sin subir archivos.

## Estructura del repositorio

```
Fase 1/                         Evidencias de la fase 1 (documentos)
Fase 2/
├── Evidencias Grupales/        Documentos del equipo
├── Evidencias Individuales/
└── Evidencias Proyecto/
    └── Evidencias de Sistema/
        ├── Aplicacion/
        │   ├── backend/                API en Python (FastAPI + Tesseract + SQLite)
        │   │   ├── app/
        │   │   │   ├── api/            Endpoints: documentos y dashboard
        │   │   │   ├── classifier/     Clasificación por palabras clave y número del documento
        │   │   │   ├── extraccion/     Lectura de la tabla de mercancías
        │   │   │   ├── services/ocr.py OCR de imágenes y PDF
        │   │   │   └── seguimiento.py  Comparación OC / guías / facturas
        │   │   └── tests/
        │   └── frontend/               Interfaz en React + Vite + Tailwind
        └── Base de Datos/              Esquema SQLite (schema.sql) y la base documatch.db
```

## Requisitos

| Herramienta | Versión | Notas |
|---|---|---|
| Python | 3.10 o superior | |
| Node.js | 18 o superior | Incluye `npm` |
| Tesseract OCR | 5.x | En Windows: [instalador de UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Durante la instalación, en *Additional language data*, hay que marcar **Spanish**. |

La ruta esperada de Tesseract es `C:\Program Files\Tesseract-OCR\tesseract.exe`. Si se instala en otra carpeta, hay que definir la variable `TESSERACT_CMD` (ver [Configuración](#configuración)).

## Instalación y ejecución

La aplicación necesita **dos terminales**: una para el backend y otra para el frontend.

### Backend

```powershell
cd "Fase 2/Evidencias Proyecto/Evidencias de Sistema/Aplicacion/backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- La API queda en http://127.0.0.1:8000.
- La documentación interactiva está en http://127.0.0.1:8000/docs.
- La base de datos SQLite se crea sola en `Evidencias de Sistema/Base de Datos/documatch.db` a partir de [schema.sql](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20Sistema/Base%20de%20Datos/schema.sql). Los archivos subidos quedan en `backend/data/archivos/`.
- La primera vez, si existe una base anterior en `backend/data/documentos.db`, sus documentos se copian a la nueva sin los duplicados.

Si PowerShell no deja ejecutar `Activate.ps1`, hay que correr esto una sola vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Frontend

```powershell
cd "Fase 2/Evidencias Proyecto/Evidencias de Sistema/Aplicacion/frontend"
npm install
npm run dev
```

Abrir http://localhost:5173. Vite reenvía las llamadas a `/api` hacia el backend, que debe estar corriendo.

> Después de cada `git pull`, conviene ejecutar `pip install -r requirements.txt` y `npm install`, por si cambiaron las dependencias.

### Tests

```powershell
cd "Fase 2/Evidencias Proyecto/Evidencias de Sistema/Aplicacion/backend"
pytest
```

## Configuración

Son variables de entorno opcionales y se definen antes de iniciar el backend:

| Variable | Por defecto | Uso |
|---|---|---|
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | Ruta al ejecutable de Tesseract |
| `OCR_LANG` | `spa` | Idiomas del OCR (por ejemplo `spa+eng`) |
| `DATA_DIR` | `backend/data` | Carpeta de los archivos subidos |
| `DB_PATH` | `Base de Datos/documatch.db` | Archivo de la base SQLite |

Ejemplo en PowerShell: `$env:TESSERACT_CMD = "D:\Tesseract\tesseract.exe"`

## Cómo funciona

1. **OCR** ([ocr.py](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20Sistema/Aplicacion/backend/app/services/ocr.py)):
   - **PDF:** si trae texto digital, lo usa directo; si es escaneado, se renderiza a 300 dpi y pasa por el OCR.
   - **Imágenes:** antes del OCR se preprocesan:
     - escala de grises que oscurece el texto de color (los títulos rojos del SII);
     - más contraste y tamaño;
     - se borran las líneas y sombreados de las tablas, que confunden a Tesseract.
2. **Clasificación** ([palabras_clave.py](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20Sistema/Aplicacion/backend/app/classifier/palabras_clave.py)):
   - cada tipo de documento suma puntos por las palabras clave que aparecen en el texto;
   - el título en el encabezado da un bono;
   - se ignoran las referencias a otros documentos (por ejemplo, la OC que cita una factura).
3. **Número del documento:** se busca junto al título o en el recuadro del SII. Se toleran las lecturas típicas del OCR para "N°", como `n*`, `n”` o `n2`.
4. **Mercancías** ([mercancias.py](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20Sistema/Aplicacion/backend/app/extraccion/mercancias.py)):
   - se busca el encabezado de la tabla que tiene la columna *Cantidad*;
   - en cada fila se lee el número que queda bajo esa columna y bajo la del valor total;
   - se usa la posición de cada palabra, no el texto plano.
5. **Conciliación** ([seguimiento.py](Fase%202/Evidencias%20Proyecto/Evidencias%20de%20Sistema/Aplicacion/backend/app/seguimiento.py)):
   - se compara la cantidad total pedida con la suma de las guías;
   - y lo despachado con la suma de las facturas.

| Estado | Significado |
|---|---|
| Conciliado | Pedido, despacho y factura coinciden |
| Despacho parcial | Se despachó menos de lo pedido (y se facturó lo despachado) |
| Discrepancia | Se despachó más de lo pedido, la factura no coincide con lo recibido, o no se pudo leer alguna cantidad |
| Pendiente | Falta la guía o la factura, sin diferencias hasta ahora |
| Finalizada | Despacho parcial que se dio por terminado |

## API principal

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/documentos` | Sube y analiza un documento. Con `orden_id` (form) se vincula a esa OC. Responde `409` si el documento ya existe. |
| `GET` | `/api/documentos` | Historial (filtro opcional `?tipo=`). |
| `GET` / `DELETE` | `/api/documentos/{id}` | Detalle o eliminación de un documento. |
| `PUT` | `/api/documentos/{id}/cantidades` | Corrige las cantidades (`{"cantidades": [...]}`, en el orden de los ítems) de una guía de despacho con confianza menor al 65 %. |
| `GET` | `/api/documentos/{id}/archivo` | Archivo original. |
| `GET` | `/api/dashboard` | Filas del dashboard con estado, cantidades y avance. |
| `POST` / `DELETE` | `/api/ordenes/{id}/finalizar` | Finaliza (con `{"motivo": "..."}` opcional) o reabre una OC. |
| `POST` / `DELETE` | `/api/dummies` | Crea (`?escenario=ok\|parcial\|discrepancia\|pendiente`) o borra datos de ejemplo. |

El detalle completo de la API está en http://127.0.0.1:8000/docs.

## Limitaciones conocidas

- **Se comparan cantidades totales, no producto por producto.** El OCR escribe la misma descripción de forma distinta en cada documento, así que emparejar ítems no es confiable. Si una guía trae 5 unidades de A en vez de 5 de B, el total coincide y no se detecta.
- **La lectura depende de la calidad de la imagen.** Las fotos borrosas, torcidas o con poca luz pueden dar cantidades o números incorrectos. Para eso existe la verificación contra el neto impreso.
- **Los duplicados se detectan por tipo y número, sin el RUT del emisor**, porque el sistema todavía no lo lee. Si dos proveedores distintos emiten la factura 123, la segunda se rechaza. Si el OCR lee mal un número, puede chocar con el de otro documento. En los dos casos el mensaje indica qué documento ya existe.
- Hay dos tests de `test_mercancias.py` que fallan desde antes de los últimos cambios: `test_borde_de_celda_pegado_al_encabezado` y `test_orden_de_compra_con_punto_decimal`.

## Equipo

- Vania González
- Víctor Mendoza
- Fabián Quezada

Planificación: [Jira](https://victormendozacl.atlassian.net/jira/plans/1/scenarios/1/timeline?vid=1)
