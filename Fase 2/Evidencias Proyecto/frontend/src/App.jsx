import { useEffect, useState } from 'react'

const NOMBRES = {
  factura: 'Factura',
  guia_despacho: 'Guía de despacho',
  orden_compra: 'Orden de compra',
}

export default function App() {
  const [archivo, setArchivo] = useState(null)
  const [resultado, setResultado] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [historial, setHistorial] = useState([])
  const [filtro, setFiltro] = useState('')

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
      cargarHistorial()
    } catch (err) {
      setError(err.message)
    } finally {
      setCargando(false)
    }
  }

  async function verDocumento(id) {
    const res = await fetch(`/api/documentos/${id}`)
    if (res.ok) setResultado(await res.json())
  }

  async function eliminar(id) {
    if (!confirm('¿Eliminar este documento?')) return
    const res = await fetch(`/api/documentos/${id}`, { method: 'DELETE' })
    if (res.ok) {
      if (resultado?.id === id) setResultado(null)
      cargarHistorial()
    }
  }

  const esPdf = resultado?.archivo?.toLowerCase().endsWith('.pdf')

  return (
    <main className="contenedor">
      <h1>Clasificador de documentos</h1>
      <p className="subtitulo">Sube una factura, guía de despacho u orden de compra (imagen o PDF).</p>

      <form onSubmit={analizar} className="formulario">
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
          onChange={(e) => setArchivo(e.target.files[0] ?? null)}
        />
        <button type="submit" disabled={!archivo || cargando}>
          {cargando ? 'Analizando…' : 'Analizar'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {resultado && (
        <section className="resultado">
          <h2>
            {resultado.nombre}
            {resultado.tipo !== 'desconocido' && (
              <span className="confianza">{Math.round(resultado.confianza * 100)}% confianza</span>
            )}
          </h2>
          <p className="archivo">
            {resultado.archivo} ·{' '}
            <a href={resultado.url_archivo} target="_blank" rel="noreferrer">Abrir original</a>
          </p>

          {!esPdf && <img className="vista-previa" src={resultado.url_archivo} alt={resultado.archivo} />}

          <table>
            <thead>
              <tr><th>Tipo</th><th>Puntaje</th><th>Palabras encontradas</th></tr>
            </thead>
            <tbody>
              {Object.entries(resultado.puntajes).map(([tipo, puntaje]) => (
                <tr key={tipo} className={tipo === resultado.tipo ? 'ganador' : ''}>
                  <td>{NOMBRES[tipo] ?? tipo}</td>
                  <td>{puntaje}</td>
                  <td>{resultado.coincidencias[tipo].join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <details>
            <summary>Ver texto extraído</summary>
            <pre>{resultado.texto}</pre>
          </details>
        </section>
      )}

      <section className="resultado">
        <div className="historial-encabezado">
          <h2>Historial</h2>
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRES).map(([tipo, nombre]) => (
              <option key={tipo} value={tipo}>{nombre}</option>
            ))}
            <option value="desconocido">Desconocido</option>
          </select>
        </div>

        {historial.length === 0 ? (
          <p className="vacio">No hay documentos guardados.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Fecha</th><th>Archivo</th><th>Tipo</th><th>Confianza</th><th></th></tr>
            </thead>
            <tbody>
              {historial.map((doc) => (
                <tr key={doc.id} className={resultado?.id === doc.id ? 'ganador' : ''}>
                  <td>{new Date(doc.fecha_creacion + 'Z').toLocaleString('es-CL')}</td>
                  <td>
                    <button className="enlace" onClick={() => verDocumento(doc.id)}>{doc.archivo}</button>
                  </td>
                  <td>{doc.nombre}</td>
                  <td>{doc.tipo === 'desconocido' ? '—' : `${Math.round(doc.confianza * 100)}%`}</td>
                  <td>
                    <button className="eliminar" onClick={() => eliminar(doc.id)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}
