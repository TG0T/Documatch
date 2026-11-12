import { useEffect, useMemo, useState } from 'react'
import { confirmar, mostrarError } from './alertas.js'
import { Icon } from './iconos.jsx'

// Nombre y colores de cada tipo de documento (los mismos tonos que en el dashboard)
const TIPOS = {
  orden_compra:  { nombre: 'Orden de compra',  chip: 'bg-slate-100 text-slate-700 ring-slate-600/20' },
  guia_despacho: { nombre: 'Guía de despacho', chip: 'bg-sky-50 text-sky-700 ring-sky-600/20' },
  factura:       { nombre: 'Factura',          chip: 'bg-violet-50 text-violet-700 ring-violet-600/20' },
  desconocido:   { nombre: 'Desconocido',      chip: 'bg-amber-50 text-amber-700 ring-amber-600/20' },
}

const EXTENSIONES = '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp'

// Solo en estos documentos se muestran los valores de cada producto
const TIPOS_CON_VALORES = ['factura', 'orden_compra']

// Cantidades en formato chileno: 1.500 / 2,5
const formatoCantidad = (n) => (n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: 3 }))
const formatoPesos = (n) => (n == null ? '—' : `$${n.toLocaleString('es-CL', { maximumFractionDigits: 2 })}`)
const fecha = (iso) => new Date(iso + 'Z')

const BOTON_PRIMARIO = 'inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40'
const BOTON_SECUNDARIO = 'inline-flex items-center justify-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50'

// Guía de despacho leída con poca confianza: se pueden corregir sus cantidades a mano. Sin tabla de
// ítems se ingresa solo el total.
export async function guardarCantidades(id, cantidades) {
  const res = await fetch(`/api/documentos/${id}/cantidades`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cantidades: cantidades.map(Number) }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisa las cantidades ingresadas')
  return data
}

// Cantidades válidas para guardar: todas números mayores o iguales a 0
export const cantidadesValidas = (valores) => valores.every((v) => v !== '' && Number(v) >= 0)

/* ══════════════════════════════════════════════════════════════
   PIEZAS
   ══════════════════════════════════════════════════════════════ */

function TipoChip({ tipo }) {
  const t = TIPOS[tipo] ?? TIPOS.desconocido
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${t.chip}`}>
      {t.nombre}
    </span>
  )
}

// Color según la confianza del OCR: verde desde 80%, ámbar desde 60%, rojo bajo eso
export const colorConfianza = (valor) => (valor >= 0.8 ? 'bg-emerald-500' : valor >= 0.6 ? 'bg-amber-400' : 'bg-rose-500')

// Barra de confianza (siempre con el número: el color solo no basta)
export function Confianza({ valor, ancho = 'w-16' }) {
  const color = colorConfianza(valor)
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-1.5 ${ancho} overflow-hidden rounded-full bg-slate-100`}>
        <span className={`block h-full rounded-full ${color}`} style={{ width: `${Math.round(valor * 100)}%` }} />
      </span>
      <span className="text-xs tabular-nums text-slate-600">{Math.round(valor * 100)}%</span>
    </span>
  )
}

// Aviso de color con ícono: tono "ok" (verde), "revisar" (ámbar) o "info" (gris)
function Aviso({ tono, icono, children, accion }) {
  const estilos = {
    ok: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
    revisar: 'bg-amber-50 text-amber-800 ring-amber-600/20',
    info: 'bg-slate-50 text-slate-700 ring-slate-600/10',
  }
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl px-3.5 py-2.5 text-sm ring-1 ring-inset ${estilos[tono]}`}>
      <span className="flex items-start gap-2">
        <Icon name={icono} className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{children}</span>
      </span>
      {accion}
    </div>
  )
}

// Compara la suma de los valores con el neto impreso en el documento, para detectar dígitos
// mal leídos por el OCR.
function Verificacion({ doc }) {
  if (doc.valores_coinciden) {
    return (
      <Aviso tono="ok" icono="check">
        La suma de los valores coincide con el neto del documento ({formatoPesos(doc.neto_documento)}).
      </Aviso>
    )
  }
  if (doc.valores_coinciden === false) {
    return (
      <Aviso tono="revisar" icono="alert">
        Revisar los valores: la suma ({formatoPesos(doc.valor_total)}) no coincide con el neto del documento
        ({formatoPesos(doc.neto_documento)}). Puede haber un dígito mal leído o un producto sin valor.
      </Aviso>
    )
  }
  return (
    <Aviso tono="revisar" icono="alert">
      No se encontró el neto en el documento: no se pudo verificar la suma de los valores.
    </Aviso>
  )
}

function ZonaCarga({ archivo, setArchivo, cargando, onAnalizar }) {
  const [arrastrando, setArrastrando] = useState(false)
  const elegir = (lista) => { if (lista?.[0]) setArchivo(lista[0]) }

  return (
    <form onSubmit={onAnalizar} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <label
        onDragOver={(e) => { e.preventDefault(); setArrastrando(true) }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => { e.preventDefault(); setArrastrando(false); if (!cargando) elegir(e.dataTransfer.files) }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          arrastrando ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 bg-slate-50/60 hover:border-indigo-300 hover:bg-indigo-50/40'
        }`}>
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-indigo-500 shadow-sm ring-1 ring-slate-200">
          <Icon name="clip" className="h-6 w-6" />
        </span>
        <span className="text-sm font-medium text-slate-700">
          Arrastra el documento aquí o <span className="text-indigo-600 underline decoration-indigo-300 underline-offset-2">búscalo en tu equipo</span>
        </span>
        <span className="text-xs text-slate-400">Factura, guía de despacho u orden de compra · PDF, PNG, JPG, TIFF o WebP</span>
        <input type="file" accept={EXTENSIONES} className="hidden" disabled={cargando}
          onChange={(e) => { elegir(e.target.files); e.target.value = '' }} />
      </label>

      {archivo && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200">
            <Icon name="doc" className="h-4 w-4 shrink-0 text-slate-400" />
            <span className="truncate">{archivo.name}</span>
            {!cargando && (
              <button type="button" onClick={() => setArchivo(null)} title="Quitar archivo"
                className="text-slate-400 transition hover:text-rose-600">
                <Icon name="x" className="h-4 w-4" />
              </button>
            )}
          </span>
          <button type="submit" disabled={cargando} className={BOTON_PRIMARIO}>
            <Icon name={cargando ? 'clock' : 'search'} />
            {cargando ? 'Analizando… puede tardar unos segundos' : 'Analizar documento'}
          </button>
        </div>
      )}
    </form>
  )
}

/* ══════════════════════════════════════════════════════════════
   RESULTADO
   ══════════════════════════════════════════════════════════════ */

function Resultado({ resultado, setResultado, onCambio, onCerrar }) {
  // Cantidades que se están editando (texto de cada input), o null si no se está editando
  const [edicion, setEdicion] = useState(null)
  useEffect(() => setEdicion(null), [resultado.id])

  const esPdf = resultado.archivo?.toLowerCase().endsWith('.pdf')
  const conValores = TIPOS_CON_VALORES.includes(resultado.tipo)
  const puntajeMaximo = Math.max(...Object.values(resultado.puntajes), 1)

  function editarCantidades() {
    const items = resultado.items
    setEdicion(items.length ? items.map((i) => String(i.cantidad ?? '')) : [String(resultado.cantidad_total ?? '')])
  }

  async function guardarEdicion() {
    try {
      setResultado(await guardarCantidades(resultado.id, edicion))
      setEdicion(null)
      onCambio()
    } catch (err) {
      mostrarError(err.message)
    }
  }

  const inputCantidad = (i) => (
    <input type="number" min="0" step="any" value={edicion[i]}
      onChange={(e) => setEdicion(edicion.map((v, j) => (j === i ? e.target.value : v)))}
      className="w-28 rounded-lg border-0 px-2 py-1 text-right text-sm tabular-nums text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-indigo-500" />
  )

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Encabezado */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-900">{resultado.nombre}</h2>
            {resultado.codigo && (
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 font-mono text-sm font-medium text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
                {resultado.codigo}
              </span>
            )}
            {resultado.dummy && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">Documento de ejemplo</span>
            )}
          </div>
          <p className="mt-1 truncate text-sm text-slate-500">{resultado.archivo}</p>
        </div>
        <div className="flex items-center gap-3">
          {resultado.tipo !== 'desconocido' && (
            <span className="flex items-center gap-2 text-xs text-slate-500">
              Confianza <Confianza valor={resultado.confianza} ancho="w-20" />
            </span>
          )}
          {!resultado.dummy && (
            <a href={resultado.url_archivo} target="_blank" rel="noreferrer" className={BOTON_SECUNDARIO}>
              <Icon name="doc" /> Abrir original
            </a>
          )}
          <button onClick={onCerrar} title="Cerrar"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
            <Icon name="x" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 p-5 lg:grid-cols-5">
        {/* Vista previa */}
        <div className="lg:col-span-2">
          {resultado.dummy ? (
            <div className="flex h-48 flex-col items-center justify-center rounded-xl bg-slate-50 text-center ring-1 ring-inset ring-slate-200">
              <Icon name="box" className="h-8 w-8 text-slate-300" />
              <p className="mt-2 text-sm text-slate-500">Documento de ejemplo, sin archivo original</p>
            </div>
          ) : esPdf ? (
            <a href={resultado.url_archivo} target="_blank" rel="noreferrer"
              className="flex h-48 flex-col items-center justify-center rounded-xl bg-slate-50 text-center ring-1 ring-inset ring-slate-200 transition hover:bg-indigo-50/40">
              <Icon name="doc" className="h-8 w-8 text-slate-400" />
              <p className="mt-2 text-sm font-medium text-indigo-600">Abrir el PDF en otra pestaña</p>
            </a>
          ) : (
            <a href={resultado.url_archivo} target="_blank" rel="noreferrer" title="Abrir en tamaño completo">
              <img src={resultado.url_archivo} alt={resultado.archivo}
                className="max-h-[520px] w-full rounded-xl object-contain object-top ring-1 ring-slate-200" />
            </a>
          )}
        </div>

        {/* Datos leídos */}
        <div className="space-y-4 lg:col-span-3">
          {resultado.tipo !== 'desconocido' && !resultado.codigo && (
            <Aviso tono="revisar" icono="alert">No se encontró el número del documento.</Aviso>
          )}
          {resultado.cantidades_editables && (
            <Aviso tono="revisar" icono="alert"
              accion={edicion ? (
                <span className="flex gap-2">
                  <button type="button" onClick={() => setEdicion(null)} className={BOTON_SECUNDARIO}>Cancelar</button>
                  <button type="button" onClick={guardarEdicion} disabled={!cantidadesValidas(edicion)} className={BOTON_PRIMARIO}>Guardar</button>
                </span>
              ) : (
                <button type="button" onClick={editarCantidades} className={BOTON_SECUNDARIO}>
                  <Icon name="pencil" /> Editar cantidades
                </button>
              )}>
              Confianza baja ({Math.round(resultado.confianza * 100)}%): compara las cantidades con el original y
              corrígelas si es necesario.
            </Aviso>
          )}
          {resultado.cantidades_editadas && (
            <Aviso tono="info" icono="pencil">Las cantidades se corrigieron a mano.</Aviso>
          )}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Mercancías</h3>
            {resultado.items.length === 0 ? (
              edicion ? (
                <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-inset ring-slate-200">
                  Total de unidades despachadas {inputCantidad(0)}
                </div>
              ) : (
                <div className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 ring-1 ring-inset ring-slate-200">
                  No se encontró una tabla de ítems con columna de cantidad.
                </div>
              )
            ) : (
              <div className="overflow-hidden rounded-xl ring-1 ring-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5 text-left font-semibold">Descripción</th>
                      <th className="px-4 py-2.5 text-right font-semibold">Cantidad</th>
                      {conValores && <th className="px-4 py-2.5 text-right font-semibold">Valor total</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {resultado.items.map((item, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2.5 text-slate-700">{item.descripcion || '—'}</td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums text-slate-900">
                          {edicion ? inputCantidad(i) : formatoCantidad(item.cantidad)}
                        </td>
                        {conValores && (
                          <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums text-slate-900">{formatoPesos(item.total)}</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="border-t-2 border-slate-200 bg-slate-50/60 font-semibold text-slate-900">
                    <tr>
                      <td className="px-4 py-2.5">Total · {resultado.items.length} {resultado.items.length === 1 ? 'ítem' : 'ítems'}</td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums">
                        {formatoCantidad(edicion && cantidadesValidas(edicion)
                          ? edicion.reduce((suma, v) => suma + Number(v), 0)
                          : resultado.cantidad_total)}
                      </td>
                      {conValores && <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums">{formatoPesos(resultado.valor_total)}</td>}
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
          {conValores && resultado.items.length > 0 && <Verificacion doc={resultado} />}
        </div>
      </div>

      {/* Detalle técnico: por qué se clasificó así y el texto leído */}
      <div className="grid grid-cols-1 gap-6 border-t border-slate-100 p-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-900">¿Por qué se clasificó así?</h3>
          {Object.keys(resultado.puntajes).length === 0 && (
            <p className="text-sm text-slate-500">Este documento no pasó por el clasificador (es un documento de ejemplo).</p>
          )}
          <div className="space-y-3">
            {Object.entries(resultado.puntajes).map(([tipo, puntaje]) => {
              const ganador = tipo === resultado.tipo
              return (
                <div key={tipo}>
                  <div className="flex items-center justify-between text-sm">
                    <span className={ganador ? 'font-semibold text-slate-900' : 'text-slate-600'}>
                      {TIPOS[tipo]?.nombre ?? tipo}
                      {ganador && <Icon name="check" className="ml-1 inline h-4 w-4 text-emerald-600" />}
                    </span>
                    <span className="text-xs tabular-nums text-slate-500">{puntaje} pts</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${ganador ? 'bg-indigo-500' : 'bg-slate-300'}`}
                         style={{ width: `${(puntaje / puntajeMaximo) * 100}%` }} />
                  </div>
                  {resultado.coincidencias[tipo]?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {resultado.coincidencias[tipo].map((palabra, i) => (
                        <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">{palabra}</span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm font-semibold text-slate-900">
            <Icon name="chevR" className="h-4 w-4 text-slate-400 transition group-open:rotate-90" />
            Texto extraído por el OCR
          </summary>
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-700 ring-1 ring-inset ring-slate-200">
            {resultado.texto}
          </pre>
        </details>
      </div>
    </section>
  )
}

/* ══════════════════════════════════════════════════════════════
   VISTA
   ══════════════════════════════════════════════════════════════ */

export default function App() {
  const [archivo, setArchivo] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [historial, setHistorial] = useState([])
  const [filtro, setFiltro] = useState('')
  const [busqueda, setBusqueda] = useState('')

  async function cargarHistorial() {
    try {
      const params = filtro ? `?tipo=${filtro}` : ''
      const res = await fetch(`/api/documentos${params}`)
      if (res.ok) setHistorial(await res.json())
    } catch {
      setError('No se pudo conectar con el servidor')
    }
  }

  useEffect(() => {
    cargarHistorial()
  }, [filtro])

  const visibles = useMemo(() => {
    const termino = busqueda.trim().toLowerCase()
    if (!termino) return historial
    return historial.filter((d) => `${d.archivo} ${d.codigo ?? ''}`.toLowerCase().includes(termino))
  }, [historial, busqueda])

  async function analizar(e) {
    e.preventDefault()
    if (!archivo) return
    setCargando(true)
    setError('')
    setResultado(null)

    const form = new FormData()
    form.append('archivo', archivo)
    try {
      const res = await fetch('/api/documentos', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Error al analizar el documento')
      setResultado(data)
      setArchivo(null)
      cargarHistorial()
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  async function verDocumento(id) {
    const res = await fetch(`/api/documentos/${id}`)
    if (res.ok) {
      setResultado(await res.json())
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  async function eliminar(id) {
    const ok = await confirmar({
      titulo: '¿Eliminar este documento?',
      texto: 'Se borran el registro y el archivo original.',
      boton: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    const res = await fetch(`/api/documentos/${id}`, { method: 'DELETE' })
    if (res.ok) {
      if (resultado?.id === id) setResultado(null)
      cargarHistorial()
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Clasificador de documentos</h1>
        <p className="mt-1 text-sm text-slate-500">
          Sube un documento y el sistema reconoce su tipo, su número, sus mercancías y sus valores.
        </p>
      </div>

      <ZonaCarga archivo={archivo} setArchivo={setArchivo} cargando={cargando} onAnalizar={analizar} />

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError('')} className="text-rose-400 hover:text-rose-700"><Icon name="x" /></button>
        </div>
      )}

      {resultado && (
        <Resultado resultado={resultado} setResultado={setResultado} onCambio={cargarHistorial}
          onCerrar={() => setResultado(null)} />
      )}

      {/* Historial */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Historial</h2>
            <p className="mt-0.5 text-xs text-slate-500">{visibles.length} de {historial.length} documentos</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                <Icon name="search" />
              </span>
              <input type="search" value={busqueda} onChange={(e) => setBusqueda(e.target.value)}
                placeholder="Buscar N° o archivo…"
                className="w-60 rounded-lg border-0 py-2 pl-9 pr-3 text-sm text-slate-900 ring-1 ring-inset ring-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <select value={filtro} onChange={(e) => setFiltro(e.target.value)}
              className="rounded-lg border-0 py-2 pl-3 pr-8 text-sm text-slate-700 ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-indigo-500">
              <option value="">Todos los tipos</option>
              {Object.entries(TIPOS).map(([tipo, t]) => (
                <option key={tipo} value={tipo}>{t.nombre}</option>
              ))}
            </select>
          </div>
        </div>

        {visibles.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <Icon name="doc" className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 text-sm font-medium text-slate-700">
              {historial.length === 0 ? 'Aún no hay documentos' : 'Ningún documento coincide con la búsqueda'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-5 py-2.5 text-left font-semibold">Documento</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Tipo</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Confianza</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Cantidad</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Valor total</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Fecha</th>
                  <th className="px-5 py-2.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visibles.map((doc) => {
                  const seleccionado = resultado?.id === doc.id
                  return (
                    <tr key={doc.id} onClick={() => verDocumento(doc.id)}
                      className={`cursor-pointer transition ${seleccionado ? 'bg-indigo-50/60' : 'hover:bg-slate-50'}`}>
                      <td className="max-w-[260px] px-5 py-3">
                        <p className="font-medium text-slate-900">{doc.codigo ?? 'Sin número'}</p>
                        <p className="truncate text-xs text-slate-500" title={doc.archivo}>{doc.archivo}</p>
                      </td>
                      <td className="px-3 py-3"><TipoChip tipo={doc.tipo} /></td>
                      <td className="px-3 py-3">
                        {doc.tipo === 'desconocido' ? <span className="text-slate-400">—</span> : <Confianza valor={doc.confianza} />}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-700">{formatoCantidad(doc.cantidad_total)}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-slate-700">
                        {formatoPesos(doc.valor_total)}
                        {doc.valores_coinciden === false && (
                          <span title="La suma no coincide con el neto del documento: revisar">
                            <Icon name="alert" className="ml-1 inline h-4 w-4 text-amber-500" />
                          </span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">
                        <p>{fecha(doc.fecha_creacion).toLocaleDateString('es-CL')}</p>
                        <p>{fecha(doc.fecha_creacion).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}</p>
                      </td>
                      <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <button onClick={() => eliminar(doc.id)} title="Eliminar documento"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600">
                          <Icon name="trash" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
