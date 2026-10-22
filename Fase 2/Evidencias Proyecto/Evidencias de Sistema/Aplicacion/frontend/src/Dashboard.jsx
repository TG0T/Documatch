import { useEffect, useMemo, useState } from 'react'
import App, { cantidadesValidas, guardarCantidades } from './App.jsx'
import { confirmar, mostrarError, pedirTexto } from './alertas.js'

/* ══════════════════════════════════════════════════════════════
   CONFIGURACIÓN · Escenarios y estados
   ══════════════════════════════════════════════════════════════ */

const ESCENARIOS = [
  ['ok', 'OC completa (ok)'],
  ['parcial', 'OC con despacho parcial'],
  ['discrepancia', 'OC con discrepancia en factura'],
  ['pendiente', 'OC pendiente (sin guía ni factura)'],
  ['baja_confianza', 'Guía con baja confianza (editable)'],
]

const ESTADOS = {
  ok:           { texto: 'Conciliado',       tone: 'emerald', icon: 'check' },
  parcial:      { texto: 'Despacho parcial', tone: 'amber',   icon: 'clock' },
  discrepancia: { texto: 'Discrepancia',     tone: 'rose',    icon: 'alert' },
  pendiente:    { texto: 'Pendiente',        tone: 'sky',     icon: 'truck' },
  finalizada:   { texto: 'Finalizada',       tone: 'slate',   icon: 'check' },
}

const TONES = {
  emerald: {
    bg: 'bg-emerald-50', text: 'text-emerald-700', ring: 'ring-emerald-600/20',
    dot: 'bg-emerald-500', chipBg: 'bg-emerald-50', chipText: 'text-emerald-700',
    chipRing: 'ring-emerald-600/20', grad: 'from-emerald-500 to-teal-400',
    soft: 'bg-gradient-to-br from-emerald-50 to-white',
  },
  amber: {
    bg: 'bg-amber-50', text: 'text-amber-700', ring: 'ring-amber-600/20',
    dot: 'bg-amber-500', chipBg: 'bg-amber-50', chipText: 'text-amber-700',
    chipRing: 'ring-amber-600/20', grad: 'from-amber-500 to-orange-400',
    soft: 'bg-gradient-to-br from-amber-50 to-white',
  },
  rose: {
    bg: 'bg-rose-50', text: 'text-rose-700', ring: 'ring-rose-600/20',
    dot: 'bg-rose-500', chipBg: 'bg-rose-50', chipText: 'text-rose-700',
    chipRing: 'ring-rose-600/20', grad: 'from-rose-500 to-pink-500',
    soft: 'bg-gradient-to-br from-rose-50 to-white',
  },
  sky: {
    bg: 'bg-sky-50', text: 'text-sky-700', ring: 'ring-sky-600/20',
    dot: 'bg-sky-500', chipBg: 'bg-sky-50', chipText: 'text-sky-700',
    chipRing: 'ring-sky-600/20', grad: 'from-sky-500 to-indigo-500',
    soft: 'bg-gradient-to-br from-sky-50 to-white',
  },
  violet: {
    bg: 'bg-violet-50', text: 'text-violet-700', ring: 'ring-violet-600/20',
    dot: 'bg-violet-500', chipBg: 'bg-violet-50', chipText: 'text-violet-700',
    chipRing: 'ring-violet-600/20', grad: 'from-violet-500 to-fuchsia-500',
    soft: 'bg-gradient-to-br from-violet-50 to-white',
  },
  slate: {
    bg: 'bg-slate-100', text: 'text-slate-700', ring: 'ring-slate-600/20',
    dot: 'bg-slate-500', chipBg: 'bg-slate-100', chipText: 'text-slate-700',
    chipRing: 'ring-slate-600/20', grad: 'from-slate-700 to-slate-500',
    soft: 'bg-gradient-to-br from-slate-100 to-white',
  },
}

const formatoCantidad = (n) =>
  n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: 3 })

/* ══════════════════════════════════════════════════════════════
   API
   ══════════════════════════════════════════════════════════════ */

async function subir(archivo, ordenId) {
  const form = new FormData()
  form.append('archivo', archivo)
  if (ordenId != null) form.append('orden_id', ordenId)
  const res = await fetch('/api/documentos', { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Error al analizar el documento')
  return data
}

/* ══════════════════════════════════════════════════════════════
   ICONOS (SVG inline)
   ══════════════════════════════════════════════════════════════ */

function Icon({ name, className = 'h-4 w-4' }) {
  const paths = {
    check:   <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />,
    clock:   <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />,
    alert:   <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />,
    truck:   <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 18.75a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 0 1-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 0 0-3.213-9.193 2.056 2.056 0 0 0-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 0 0-10.026 0 1.106 1.106 0 0 0-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12" />,
    search:  <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />,
    x:       <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />,
    chevR:   <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />,
    chevD:   <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />,
    plus:    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />,
    refresh: <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />,
    clip:    <path strokeLinecap="round" strokeLinejoin="round" d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13" />,
    doc:     <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />,
    box:     <path strokeLinecap="round" strokeLinejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />,
    pencil:  <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />,
    trash:   <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />,
  }
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
         strokeWidth="1.8" stroke="currentColor" className={className}>
      {paths[name]}
    </svg>
  )
}

/* ══════════════════════════════════════════════════════════════
   COMPONENTES ATÓMICOS
   ══════════════════════════════════════════════════════════════ */

function EstadoBadge({ estado }) {
  const e = ESTADOS[estado] ?? ESTADOS.pendiente
  const t = TONES[e.tone]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${t.bg} ${t.text} ${t.ring}`}>
      <Icon name={e.icon} className="h-3.5 w-3.5" />
      {e.texto}
    </span>
  )
}

function DocumentoChip({ doc, tono = 'slate' }) {
  const t = TONES[tono]
  const label = doc.codigo ?? doc.archivo
  const contenido = (
    <>
      <Icon name="doc" className="h-3 w-3 opacity-70" />
      <span className="font-semibold">{label}</span>
      {doc.cantidad_total != null && (
        <>
          <span className="opacity-40">·</span>
          <span className="tabular-nums">{formatoCantidad(doc.cantidad_total)} u.</span>
        </>
      )}
    </>
  )
  if (doc.url_archivo) {
    return (
      <a href={doc.url_archivo} target="_blank" rel="noreferrer"
         title={`Abrir ${label}`}
         className={`chip inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ring-1 ring-inset transition hover:shadow-sm ${t.chipBg} ${t.chipText} ${t.chipRing}`}>
        {contenido}
      </a>
    )
  }
  return (
    <span className={`chip inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ring-1 ring-inset ${t.chipBg} ${t.chipText} ${t.chipRing}`}>
      {contenido}
    </span>
  )
}

function KpiCard({ titulo, valor, sub, tono, icono, activo, onClick }) {
  const t = TONES[tono]
  return (
    <button type="button" onClick={onClick}
      className={`group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-xl ${activo ? 'ring-2 ring-slate-900/10' : ''}`}>
      {/* Línea superior con gradiente (siempre visible) */}
      <span className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${t.grad}`} />
      {/* Resplandor radial sutil al hacer hover */}
      <span className={`pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br ${t.grad} opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-20`} />
      <div className="flex items-start justify-between">
        <span className={`flex h-10 w-10 items-center justify-center rounded-xl ring-1 ring-inset ${t.bg} ${t.text} ${t.ring}`}>
          <Icon name={icono} className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-4 text-sm font-medium text-slate-500">{titulo}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums text-slate-900">{valor}</p>
      {sub && <p className="mt-2 text-xs text-slate-400">{sub}</p>}
      <span className={`absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r ${t.grad} transition ${activo ? 'opacity-100' : 'opacity-0 group-hover:opacity-60'}`} />
    </button>
  )
}

/* ══════════════════════════════════════════════════════════════
   MODAL DE CARGA
   ══════════════════════════════════════════════════════════════ */

function ModalCarga({ abierto, onClose, onSubir, contexto }) {
  const [archivos, setArchivos] = useState([])
  const [dragging, setDragging] = useState(false)
  const [subiendo, setSubiendo] = useState(0) // n° del archivo que se está analizando (0: ninguno)

  useEffect(() => {
    if (!abierto) { setArchivos([]); setDragging(false); setSubiendo(0) }
  }, [abierto])

  if (!abierto) return null

  const addFiles = (fileList) => {
    const arr = Array.from(fileList ?? []).filter(Boolean)
    if (arr.length) setArchivos((prev) => [...prev, ...arr])
  }

  // Mientras se analiza no se puede cerrar ni volver a enviar (se subirían duplicados)
  const cerrar = () => { if (!subiendo) onClose() }

  const submit = async () => {
    if (subiendo) return
    setSubiendo(1)
    try {
      await onSubir(archivos, setSubiendo)
    } finally {
      setSubiendo(0)
    }
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={cerrar} />
      <div className="relative flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-slate-900/5">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Adjuntar documento</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {contexto ? <>Se vinculará a <b>{contexto}</b></> : 'Sube una OC, guía de despacho o factura'}
            </p>
          </div>
          <button onClick={cerrar} disabled={subiendo > 0}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700">
            <Icon name="x" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); if (!subiendo) addFiles(e.dataTransfer.files) }}
            onClick={() => { if (!subiendo) document.getElementById('modal-file-input')?.click() }}
            className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${dragging ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 bg-gradient-to-br from-slate-50 to-white hover:border-indigo-300 hover:from-indigo-50/40'}`}>
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-indigo-500 shadow-sm ring-1 ring-slate-200">
              <Icon name="clip" className="h-5 w-5" />
            </span>
            <p className="text-sm font-medium text-slate-700">
              Arrastra el archivo aquí o{' '}
              <span className="underline decoration-indigo-300 underline-offset-2">búscalo</span>
            </p>
            <p className="text-xs text-slate-400">PDF, PNG, JPG, TIFF o WebP</p>
          </div>
          <input
            id="modal-file-input"
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
            className="hidden"
            onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
          />

          {archivos.length > 0 && (
            <ul className="space-y-2">
              {archivos.map((f, i) => (
                <li key={i} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs ring-1 ring-inset ring-slate-200">
                  <Icon name="doc" className="h-3.5 w-3.5 text-slate-400" />
                  <span className="flex-1 truncate text-slate-700">{f.name}</span>
                  {subiendo === i + 1 && <span className="text-indigo-600">Analizando…</span>}
                  {subiendo > i + 1 && <Icon name="check" className="h-3.5 w-3.5 text-emerald-600" />}
                  <button onClick={() => setArchivos((a) => a.filter((_, j) => j !== i))} disabled={subiendo > 0}
                    className="text-slate-400 disabled:invisible transition hover:text-rose-600">
                    <Icon name="x" className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3.5">
          <button onClick={cerrar} disabled={subiendo > 0}
            className="rounded-lg bg-white disabled:opacity-40 px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50">
            Cancelar
          </button>
          <button onClick={submit} disabled={archivos.length === 0 || subiendo > 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40">
            <Icon name={subiendo ? 'clock' : 'check'} />
            {subiendo
              ? `Analizando ${subiendo} de ${archivos.length}…`
              : `Adjuntar ${archivos.length > 1 ? `(${archivos.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   FILA EXPANDIBLE (ACORDEÓN)
   ══════════════════════════════════════════════════════════════ */

// Ítems de un documento. Una guía de despacho leída con poca confianza permite corregir sus
// cantidades (sin tabla de ítems, solo el total).
function ItemsDocumento({ doc, onCambio }) {
  const [edicion, setEdicion] = useState(null)

  function editar() {
    setEdicion(doc.items.length ? doc.items.map((i) => String(i.cantidad ?? '')) : [String(doc.cantidad_total ?? '')])
  }

  async function guardar() {
    try {
      await guardarCantidades(doc.id, edicion)
      setEdicion(null)
      onCambio()
    } catch (err) {
      mostrarError(err.message)
    }
  }

  const input = (i) => (
    <input type="number" min="0" step="any" value={edicion[i]}
      onChange={(e) => setEdicion(edicion.map((v, j) => (j === i ? e.target.value : v)))}
      className="w-20 rounded-md border-0 px-1.5 py-0.5 text-right text-xs tabular-nums text-slate-900 ring-1 ring-inset ring-slate-300 focus:ring-2 focus:ring-indigo-500" />
  )

  return (
    <>
      {doc.cantidades_editables && (
        <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-800 ring-1 ring-inset ring-amber-600/20">
          <span>Confianza baja ({Math.round(doc.confianza * 100)}%)</span>
          {edicion ? (
            <span className="flex gap-1">
              <button onClick={() => setEdicion(null)}
                className="rounded px-1.5 py-0.5 font-medium text-slate-600 hover:bg-white">Cancelar</button>
              <button onClick={guardar} disabled={!cantidadesValidas(edicion)}
                className="rounded bg-slate-900 px-1.5 py-0.5 font-medium text-white hover:bg-slate-800 disabled:opacity-40">Guardar</button>
            </span>
          ) : (
            <button onClick={editar} title="Corregir las cantidades leídas por el OCR"
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium hover:bg-white">
              <Icon name="pencil" className="h-3 w-3" /> Editar cantidades
            </button>
          )}
        </div>
      )}
      {doc.cantidades_editadas && !edicion && (
        <p className="mt-1 text-[11px] italic text-slate-500">Cantidades corregidas a mano</p>
      )}
      {doc.items.length === 0 ? (
        edicion ? (
          <p className="mt-1.5 flex items-center justify-between gap-3 text-xs text-slate-600">Total despachado {input(0)}</p>
        ) : (
          <p className="mt-1.5 text-[11px] italic text-slate-400">No se encontró la tabla de ítems</p>
        )
      ) : (
        <ul className="mt-1.5 divide-y divide-slate-100 text-xs">
          {doc.items.map((it, i) => (
            <li key={i} className="flex items-start justify-between gap-3 py-1">
              <span className="text-slate-600">{it.descripcion || '—'}</span>
              {edicion
                ? input(i)
                : <span className="shrink-0 tabular-nums font-medium text-slate-800">{formatoCantidad(it.cantidad)}</span>}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

// Una columna del desglose: los ítems de la OC, de sus guías o de sus facturas
function ColumnaItems({ titulo, total, docs, tono, onCambio }) {
  const t = TONES[tono]
  return (
    <div className="p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h5 className={`text-[11px] font-semibold uppercase tracking-wider ${t.text}`}>{titulo}</h5>
        <span className="text-xs tabular-nums text-slate-500">
          Total: <b className="text-slate-800">{formatoCantidad(total)}</b>
        </span>
      </div>
      {docs.length === 0 ? (
        <p className="text-xs italic text-slate-400">Sin documentos</p>
      ) : (
        <div className="space-y-3">
          {docs.map((doc) => (
            <div key={doc.id}>
              <DocumentoChip doc={doc} tono={tono} />
              <ItemsDocumento doc={doc} onCambio={onCambio} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function FilaOC({ fila, onEliminar, onSubirDoc, onFinalizar, onReabrir, onCambio }) {
  const [abierta, setAbierta] = useState(false)
  const id = fila.orden.id
  const codigo = fila.orden.codigo ?? '(sin número)'
  const estado = ESTADOS[fila.estado] ?? ESTADOS.pendiente

  // Porcentaje de lo pedido que ya se despachó (null: sin guías o sin cantidades legibles)
  const progreso = fila.avance

  return (
    <>
      <tr className={`group cursor-pointer transition ${abierta ? 'bg-gradient-to-r from-slate-50 to-white' : 'hover:bg-slate-50/60'}`}
          onClick={() => setAbierta((v) => !v)}>
        <td className="px-4 py-3 align-middle">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded text-slate-400 transition group-hover:text-slate-700">
            <Icon name={abierta ? 'chevD' : 'chevR'} className="h-4 w-4" />
          </span>
        </td>
        <td className="px-3 py-3 align-top">
          <div className="flex flex-col gap-0.5">
            <span className="font-semibold text-slate-900">{codigo}</span>
            <span className="text-xs text-slate-500">
              {fila.orden.cantidad_total != null
                ? `${formatoCantidad(fila.orden.cantidad_total)} u. totales`
                : 'Sin total'}
            </span>
          </div>
        </td>
        <td className="px-3 py-3 align-top">
          <EstadoBadge estado={fila.estado} />
        </td>
        <td className="px-3 py-3 align-top" onClick={(e) => e.stopPropagation()}>
          <div className="flex flex-wrap items-center gap-1.5">
            {fila.guias.length === 0 && fila.facturas.length === 0 && (
              <span className="text-xs italic text-slate-400">Sin documentos</span>
            )}
            {fila.guias.map((g) => <DocumentoChip key={g.id} doc={g} tono="sky" />)}
            {fila.facturas.map((f) => <DocumentoChip key={f.id} doc={f} tono="violet" />)}
            <button onClick={() => onSubirDoc(id, codigo)}
              title="Adjuntar guía o factura"
              className="inline-flex items-center gap-1 rounded-md border border-dashed border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-500 transition hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-700">
              <Icon name="plus" className="h-3 w-3" />
              Adjuntar
            </button>
          </div>
        </td>
        <td className="px-3 py-3 align-top">
          <div className="flex items-center gap-2 min-w-[140px]"
               title={`Despachado ${formatoCantidad(fila.despachado)} de ${formatoCantidad(fila.pedido)}`}>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full bg-gradient-to-r ${TONES[estado.tone].grad} transition-all`} style={{ width: `${progreso ?? 0}%` }} />
            </div>
            <span className="w-9 text-right text-xs tabular-nums text-slate-500">{progreso == null ? '—' : `${progreso}%`}</span>
          </div>
        </td>
        <td className="px-3 py-3 align-top text-right text-xs text-slate-500">
          {fila.detalle || '—'}
        </td>
        <td className="px-4 py-3 align-top text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
          {/* Opcional: cerrar un despacho parcial ya facturado (acuerdo con el proveedor) */}
          {fila.puede_finalizar && (
            <button onClick={() => onFinalizar(id, codigo)}
              title="Dar por terminada la orden con lo recibido"
              className="mr-1 inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-900 hover:text-white">
              <Icon name="check" className="h-3.5 w-3.5" /> Finalizar
            </button>
          )}
          {fila.finalizada && (
            <button onClick={() => onReabrir(id, codigo)}
              title="Volver a dejar la orden abierta"
              className="mr-1 inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1.5 text-xs font-medium text-slate-500 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50 hover:text-slate-800">
              <Icon name="refresh" className="h-3.5 w-3.5" /> Reabrir
            </button>
          )}
          <button onClick={() => onEliminar(id, codigo)}
            title="Eliminar orden"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-rose-50 hover:text-rose-600">
            <Icon name="trash" />
          </button>
        </td>
      </tr>

      {abierta && (
        <tr className="bg-slate-50/60">
          <td colSpan={7} className="px-4 pb-4 pt-1">
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-4 py-2.5">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Desglose de ítems · {codigo}
                </h4>
                <span className="text-[11px] text-slate-400">Ítems tal como los leyó el OCR en cada documento</span>
              </div>

              <div className="grid grid-cols-1 divide-y divide-slate-100 md:grid-cols-3 md:divide-x md:divide-y-0">
                <ColumnaItems titulo="Pedido (OC)" total={fila.pedido} docs={[fila.orden]} tono="slate" onCambio={onCambio} />
                <ColumnaItems titulo="Recibido (guías)" total={fila.despachado} docs={fila.guias} tono="sky" onCambio={onCambio} />
                <ColumnaItems titulo="Facturado" total={fila.facturado} docs={fila.facturas} tono="violet" onCambio={onCambio} />
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

/* ══════════════════════════════════════════════════════════════
   TABLERO PRINCIPAL
   ══════════════════════════════════════════════════════════════ */

function Tablero({ filas, recargar, mensaje, setMensaje }) {
  const [q, setQ] = useState('')
  const [tab, setTab] = useState('todos')
  const [modal, setModal] = useState({ open: false, ordenId: null, contexto: '' })

  const filtradas = useMemo(() => {
    const term = q.trim().toLowerCase()
    return filas.filter((f) => {
      if (tab !== 'todos' && f.estado !== tab) return false
      if (!term) return true
      const hay = [
        f.orden?.codigo,
        ...(f.guias ?? []).map((g) => g.codigo),
        ...(f.facturas ?? []).map((x) => x.codigo),
      ].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(term)
    })
  }, [filas, q, tab])

  const kpis = useMemo(() => ({
    total:        filas.length,
    ok:           filas.filter((f) => f.estado === 'ok').length,
    parcial:      filas.filter((f) => f.estado === 'parcial').length,
    discrepancia: filas.filter((f) => f.estado === 'discrepancia').length,
    pendiente:    filas.filter((f) => f.estado === 'pendiente').length,
    finalizada:   filas.filter((f) => f.estado === 'finalizada').length,
  }), [filas])

  const counts = { todos: filas.length, ok: kpis.ok, parcial: kpis.parcial, discrepancia: kpis.discrepancia, pendiente: kpis.pendiente, finalizada: kpis.finalizada }

  const TABS = [
    ['todos', 'Todos'],
    ['pendiente', 'Pendientes'],
    ['parcial', 'Parciales'],
    ['discrepancia', 'Con discrepancias'],
    ['ok', 'Conciliados'],
    ['finalizada', 'Finalizadas'],
  ]

  // Sube un archivo y devuelve el mensaje con el resultado
  async function cargar(archivo, ordenId) {
    try {
      const doc = await subir(archivo, ordenId)
      if (doc.tipo === 'orden_compra') return `✓ Se agregó la OC ${doc.codigo ?? '(sin número)'}.`
      if (doc.orden_id) return `✓ ${doc.nombre} ${doc.codigo ?? ''} agregada.`
      if (doc.tipo === 'desconocido') return '⚠ No se reconoció el tipo de documento. Quedó en el historial del clasificador.'
      return `⚠ ${doc.nombre} ${doc.codigo ?? ''}: no menciona ninguna OC del dashboard.`
    } catch (err) {
      return `✗ Error: ${err.message}`
    }
  }

  // Sube los archivos de a uno (el OCR es lento) y muestra el resultado de todos juntos
  async function cargarVarios(archivos, ordenId, alAvanzar) {
    setMensaje('')
    const mensajes = []
    for (const [i, archivo] of archivos.entries()) {
      alAvanzar(i + 1)
      const mensaje = await cargar(archivo, ordenId)
      mensajes.push(archivos.length > 1 ? `${archivo.name}: ${mensaje}` : mensaje)
    }
    setMensaje(mensajes.join('\n'))
    recargar()
  }

  async function finalizar(id, codigo) {
    const motivo = await pedirTexto({
      titulo: `¿Finalizar ${codigo}?`,
      texto: 'La orden se dará por terminada con lo recibido y facturado hasta ahora.',
      etiqueta: 'Motivo (opcional)',
      valor: 'Acuerdo con proveedor',
      boton: 'Finalizar',
    })
    if (motivo === null) return
    const res = await fetch(`/api/ordenes/${id}/finalizar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ motivo }),
    })
    if (!res.ok) await mostrarError((await res.json()).detail ?? 'No se pudo finalizar la orden')
    recargar()
  }

  async function reabrir(id, codigo) {
    const ok = await confirmar({
      titulo: `¿Reabrir ${codigo}?`,
      texto: 'Volverá a quedar como despacho parcial, esperando más guías o facturas.',
      boton: 'Reabrir',
    })
    if (!ok) return
    await fetch(`/api/ordenes/${id}/finalizar`, { method: 'DELETE' })
    recargar()
  }

  async function eliminar(id, codigo) {
    const ok = await confirmar({
      titulo: `¿Eliminar ${codigo}?`,
      texto: 'Se borra la orden de compra. Sus guías y facturas quedan en el historial del clasificador.',
      boton: 'Eliminar',
      peligro: true,
    })
    if (!ok) return
    await fetch(`/api/documentos/${id}`, { method: 'DELETE' })
    recargar()
  }

  const limpiar = () => { setQ(''); setTab('todos') }

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bg-gradient-to-r from-slate-900 via-indigo-700 to-sky-600 bg-clip-text text-2xl font-bold tracking-tight text-transparent">
            Dashboard Documatch
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Cruce entre Adquisiciones, Guías de Despacho y Facturas de proveedor.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={recargar}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50">
            <Icon name="refresh" /> Sincronizar
          </button>
          <button onClick={() => setModal({ open: true, ordenId: null, contexto: '' })}
            className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-600 to-sky-600 px-3.5 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-500 hover:to-sky-500">
            <Icon name="plus" /> Nueva carga
          </button>
        </div>
      </div>

      {/* Mensaje */}
      {mensaje && (
        <div className="flex items-start gap-3 rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50 to-white px-4 py-3 text-sm text-slate-700 shadow-sm">
          <span className="flex-1 whitespace-pre-line">{mensaje}</span>
          <button onClick={() => setMensaje('')} className="text-slate-400 transition hover:text-slate-700">
            <Icon name="x" />
          </button>
        </div>
      )}

      {/* KPIs */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard titulo="Adquisiciones"       valor={kpis.total}        sub="Total en el dashboard" tono="slate"   icono="box"   activo={tab==='todos'}         onClick={() => setTab('todos')} />
        <KpiCard titulo="Conciliadas"         valor={kpis.ok}           sub="Match completo"             tono="emerald" icono="check" activo={tab==='ok'}            onClick={() => setTab('ok')} />
        <KpiCard titulo="Entregas parciales"  valor={kpis.parcial}      sub="Despacho incompleto"        tono="amber"   icono="clock" activo={tab==='parcial'}       onClick={() => setTab('parcial')} />
        <KpiCard titulo="Discrepancias"       valor={kpis.discrepancia} sub="Revisar precio/cantidad"    tono="rose"    icono="alert" activo={tab==='discrepancia'} onClick={() => setTab('discrepancia')} />
        <KpiCard titulo="Pendientes"          valor={kpis.pendiente}    sub="Sin guía asociada"          tono="sky"     icono="truck" activo={tab==='pendiente'}     onClick={() => setTab('pendiente')} />
        <KpiCard titulo="Finalizadas"         valor={kpis.finalizada}   sub="Cerradas con despacho parcial" tono="slate" icono="check" activo={tab==='finalizada'}  onClick={() => setTab('finalizada')} />
      </section>

      {/* Filtros y búsqueda */}
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <div className="relative w-full xl:max-w-sm">
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
              <Icon name="search" />
            </span>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Buscar N° OC, guía o factura…"
              className="w-full rounded-lg border-0 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 ring-1 ring-inset ring-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          </div>

          {/* Tabs: seleccionado = blanco/negro, no seleccionado = negro/blanco */}
          <div className="flex flex-wrap items-center gap-1.5">
            {TABS.map(([k, label]) => {
              const activo = tab === k
              return (
                <button key={k} onClick={() => setTab(k)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                    activo
                      ? 'bg-white text-slate-900 ring-2 ring-inset ring-slate-900 shadow-sm'
                      : 'bg-slate-900 text-white ring-1 ring-inset ring-slate-900 hover:bg-slate-800'
                  }`}>
                  {label}
                  <span className={`rounded-full px-1.5 text-[10px] font-semibold ${
                    activo ? 'bg-slate-900/10 text-slate-700' : 'bg-white/20 text-white'
                  }`}>
                    {counts[k] ?? 0}
                  </span>
                </button>
              )
            })}
          </div>

          <div className="flex flex-1 flex-wrap items-center gap-2 xl:justify-end">
            <button onClick={limpiar}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50">
              <Icon name="refresh" /> Limpiar
            </button>
          </div>
        </div>
      </section>

      {/* Tabla principal */}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1120px] border-collapse text-sm">
            <thead className="bg-gradient-to-r from-slate-50 to-indigo-50/40 text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="w-[60px] px-4 py-3 text-left"></th>
                <th className="px-3 py-3 text-left font-semibold">Orden de compra</th>
                <th className="px-3 py-3 text-left font-semibold">Estado</th>
                <th className="px-3 py-3 text-left font-semibold">Documentos asociados</th>
                <th className="px-3 py-3 text-left font-semibold">Avance</th>
                <th className="px-3 py-3 text-right font-semibold">Detalle</th>
                <th className="px-4 py-3 text-right font-semibold">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtradas.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-16 text-center">
                    <Icon name="box" className="mx-auto h-8 w-8 text-slate-300" />
                    <p className="mt-2 text-sm font-medium text-slate-700">No hay órdenes que coincidan</p>
                    <p className="mt-1 text-xs text-slate-500">Prueba a cambiar los filtros o cargar un documento nuevo.</p>
                  </td>
                </tr>
              ) : (
                filtradas.map((fila) => (
                  <FilaOC key={fila.orden.id} fila={fila}
                    onEliminar={eliminar}
                    onFinalizar={finalizar}
                    onReabrir={reabrir}
                    onCambio={recargar}
                    onSubirDoc={(ordenId, contexto) => setModal({ open: true, ordenId, contexto })} />
                ))
              )}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/30 px-4 py-3 text-xs text-slate-500">
          <p>Mostrando <span className="font-medium text-slate-700">{filtradas.length}</span> de {filas.length} órdenes</p>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-gradient-to-br from-sky-500 to-indigo-500" />Recibido
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500" />Facturado
            </span>
          </div>
        </footer>
      </section>

      <ModalCarga
        abierto={modal.open}
        onClose={() => setModal({ open: false, ordenId: null, contexto: '' })}
        onSubir={(archivos, alAvanzar) => cargarVarios(archivos, modal.ordenId, alAvanzar)}
        contexto={modal.contexto}
      />
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   DASHBOARD RAÍZ
   ══════════════════════════════════════════════════════════════ */

export default function Dashboard() {
  const [vista, setVista] = useState('dashboard')
  const [filas, setFilas] = useState([])
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')

  async function recargar() {
    try {
      const res = await fetch('/api/dashboard')
      if (!res.ok) throw new Error()
      setFilas(await res.json())
      setError('')
    } catch {
      setError('No se pudo conectar con el servidor')
    }
  }

  useEffect(() => { recargar() }, [])

  async function agregarDummy(escenario) {
    await fetch(`/api/dummies?escenario=${escenario}`, { method: 'POST' })
    setVista('dashboard')
    recargar()
  }

  async function borrarDummies() {
    const ok = await confirmar({
      titulo: '¿Borrar todos los dummies?',
      texto: 'Se eliminan los documentos de ejemplo. Los documentos que subiste no se tocan.',
      boton: 'Borrar',
      peligro: true,
    })
    if (!ok) return
    await fetch('/api/dummies', { method: 'DELETE' })
    recargar()
  }

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* Sidebar negro */}
      <aside className="w-60 shrink-0 border-r border-slate-800 bg-slate-950 p-4 text-white">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-slate-900 shadow-lg shadow-white/10">
            <Icon name="box" className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold text-white">Documatch</p>
            <p className="text-xs text-slate-400">Clasificador de documentos</p>
          </div>
        </div>

        <nav className="space-y-1.5">
          {/* Seleccionado: blanco/negro · No seleccionado: negro/blanco */}
          <button onClick={() => { setVista('dashboard'); recargar() }}
            className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
              vista === 'dashboard'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'bg-slate-900 text-white ring-1 ring-inset ring-slate-800 hover:bg-slate-800'
            }`}>
            <Icon name="box" /> Dashboard
          </button>
          <button onClick={() => setVista('clasificador')}
            className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition ${
              vista === 'clasificador'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'bg-slate-900 text-white ring-1 ring-inset ring-slate-800 hover:bg-slate-800'
            }`}>
            <Icon name="doc" /> Clasificador
          </button>
        </nav>

        <div className="mt-6 border-t border-slate-800 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Dummies</p>
          <div className="space-y-1.5">
            {ESCENARIOS.map(([escenario, texto]) => (
              <button key={escenario} onClick={() => agregarDummy(escenario)}
                className="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition hover:border-slate-700 hover:bg-slate-800 hover:text-white">
                {texto}
              </button>
            ))}
            <button onClick={borrarDummies}
              className="w-full rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-rose-400 transition hover:bg-rose-500/10 hover:text-rose-300">
              Borrar dummies
            </button>
          </div>
        </div>
      </aside>

      {/* Contenido */}
      <main className="min-w-0 flex-1 bg-gradient-to-br from-slate-50 via-indigo-50/30 to-sky-50/20 px-4 py-6 sm:px-6 lg:px-8">
        {error && (
          <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}
        {vista === 'dashboard'
          ? <Tablero filas={filas} recargar={recargar} mensaje={mensaje} setMensaje={setMensaje} />
          : <App />}
      </main>
    </div>
  )
}