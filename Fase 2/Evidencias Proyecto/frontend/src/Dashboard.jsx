import { useEffect, useState } from 'react'
import App from './App.jsx'

const ESCENARIOS = [
  ['ok', 'OC completa (ok)'],
  ['parcial', 'OC con despacho parcial'],
  ['discrepancia', 'OC con discrepancia en factura'],
  ['pendiente', 'OC pendiente (sin guía ni factura)'],
]

const ESTADOS = {
  ok: { texto: 'OK', color: '#b6f2b6' },
  parcial: { texto: 'Despacho parcial', color: '#fff3a0' },
  discrepancia: { texto: 'Discrepancia', color: '#fff3a0' },
  pendiente: { texto: 'Pendiente', color: null },
}

const formatoCantidad = (n) => (n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: 3 }))

async function subir(archivo, ordenId) {
  const form = new FormData()
  form.append('archivo', archivo)
  if (ordenId != null) form.append('orden_id', ordenId)
  const res = await fetch('/api/documentos', { method: 'POST', body: form })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Error al analizar el documento')
  return data
}

// Código del documento con enlace al archivo (los dummies no tienen archivo)
function Documento({ doc }) {
  const nombre = doc.codigo ?? `(sin número) ${doc.archivo}`
  return (
    <div>
      {doc.url_archivo ? <a href={doc.url_archivo} target="_blank" rel="noreferrer">{nombre}</a> : nombre}
      {' '}· {formatoCantidad(doc.cantidad_total)} u.
    </div>
  )
}

// Lista de guías o facturas de la fila, con un input para subir otra
function Vinculados({ docs, ordenId, ocupado, onSubir }) {
  return (
    <td>
      {docs.map((d) => <Documento key={d.id} doc={d} />)}
      {ocupado ? (
        <div>Analizando…</div>
      ) : (
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
          onChange={(e) => {
            const archivo = e.target.files[0]
            e.target.value = ''
            if (archivo) onSubir(archivo, ordenId)
          }}
        />
      )}
    </td>
  )
}

function Tablero({ filas, recargar }) {
  const [archivo, setArchivo] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [ocupado, setOcupado] = useState(null) // 'general' o `${ordenId}-${columna}`

  async function cargar(archivo, ordenId, clave) {
    setOcupado(clave)
    setMensaje('')
    try {
      const doc = await subir(archivo, ordenId)
      if (doc.tipo === 'orden_compra') setMensaje(`Se agregó la orden de compra ${doc.codigo ?? '(sin número)'}.`)
      else if (doc.orden_id) setMensaje(`${doc.nombre} ${doc.codigo ?? ''} agregada a su orden de compra.`)
      else if (doc.tipo === 'desconocido') setMensaje('No se reconoció el tipo de documento. Quedó en el historial del clasificador.')
      else setMensaje(`${doc.nombre} ${doc.codigo ?? ''}: no menciona ninguna orden de compra del dashboard. Súbela desde la fila de su OC.`)
      recargar()
    } catch (err) {
      setMensaje(`Error: ${err.message}`)
    } finally {
      setOcupado(null)
    }
  }

  async function eliminar(id) {
    if (!confirm('¿Eliminar esta orden de compra? Sus guías y facturas quedan en el historial.')) return
    await fetch(`/api/documentos/${id}`, { method: 'DELETE' })
    recargar()
  }

  return (
    <div>
      <h1>Dashboard</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (archivo) cargar(archivo, null, 'general')
        }}
      >
        <p>
          Cargar documento (una orden de compra crea una fila nueva; una guía o factura que menciona
          el número de su OC se agrega a esa fila):
        </p>
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
          onChange={(e) => setArchivo(e.target.files[0] ?? null)}
        />{' '}
        <button type="submit" disabled={!archivo || ocupado === 'general'}>
          {ocupado === 'general' ? 'Analizando…' : 'Cargar'}
        </button>
      </form>
      {mensaje && <p>{mensaje}</p>}

      {filas.length === 0 ? (
        <p>No hay órdenes de compra. Carga una o agrega dummies desde el menú.</p>
      ) : (
        <table border="1" cellPadding="6" style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th>Orden de compra</th>
              <th>Guía(s) de despacho</th>
              <th>Factura(s)</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filas.map((fila) => {
              const estado = ESTADOS[fila.estado]
              const id = fila.orden.id
              return (
                <tr key={id} style={{ verticalAlign: 'top' }}>
                  <td><Documento doc={fila.orden} /></td>
                  <Vinculados docs={fila.guias} ordenId={id} ocupado={ocupado === `${id}-guias`}
                    onSubir={(a) => cargar(a, id, `${id}-guias`)} />
                  <Vinculados docs={fila.facturas} ordenId={id} ocupado={ocupado === `${id}-facturas`}
                    onSubir={(a) => cargar(a, id, `${id}-facturas`)} />
                  <td style={{ background: estado.color ?? undefined }}>
                    <b>{estado.texto}</b>
                    <div>{fila.detalle}</div>
                  </td>
                  <td><button onClick={() => eliminar(id)}>Eliminar</button></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [vista, setVista] = useState('dashboard')
  const [filas, setFilas] = useState([])
  const [error, setError] = useState('')

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

  useEffect(() => {
    recargar()
  }, [])

  async function agregarDummy(escenario) {
    await fetch(`/api/dummies?escenario=${escenario}`, { method: 'POST' })
    setVista('dashboard')
    recargar()
  }

  async function borrarDummies() {
    if (!confirm('¿Borrar todos los dummies?')) return
    await fetch('/api/dummies', { method: 'DELETE' })
    recargar()
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{ width: 240, padding: 12, borderRight: '1px solid #999', flexShrink: 0 }}>
        <h3>Menú</h3>
        <ul>
          <li><a href="#" onClick={(e) => { e.preventDefault(); setVista('dashboard'); recargar() }}>Dashboard</a></li>
          <li><a href="#" onClick={(e) => { e.preventDefault(); setVista('clasificador') }}>Clasificador</a></li>
        </ul>

        <h4>Agregar dummies</h4>
        {ESCENARIOS.map(([escenario, texto]) => (
          <p key={escenario}><button onClick={() => agregarDummy(escenario)}>{texto}</button></p>
        ))}
        <p><button onClick={borrarDummies}>Borrar dummies</button></p>
      </aside>

      <main style={{ flex: 1, padding: 12, minWidth: 0 }}>
        {error && <p>{error}</p>}
        {vista === 'dashboard' ? <Tablero filas={filas} recargar={recargar} /> : <App />}
      </main>
    </div>
  )
}
