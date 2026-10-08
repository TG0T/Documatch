import { useEffect, useState } from 'react'

const NOMBRES = {
  factura: 'Factura',
  guia_despacho: 'Guía de despacho',
  orden_compra: 'Orden de compra',
}

// Solo en estos documentos se muestran los valores de cada producto
const TIPOS_CON_VALORES = ['factura', 'orden_compra']

// Cantidades en formato chileno: 1.500 / 2,5
const formatoCantidad = (n) => (n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: 3 }))
const formatoPesos = (n) => (n == null ? '—' : `$${n.toLocaleString('es-CL', { maximumFractionDigits: 2 })}`)

// Compara la suma de los valores con el neto impreso en el documento, para detectar dígitos
// mal leídos por el OCR.
function Verificacion({ doc }) {
  if (doc.valores_coinciden) {
    return (
      <p className="verificacion ok">
        ✓ La suma de los valores coincide con el neto del documento ({formatoPesos(doc.neto_documento)}).
      </p>
    )
  }
  if (doc.valores_coinciden === false) {
    return (
      <p className="verificacion revisar">
        ⚠ Revisar los valores: la suma ({formatoPesos(doc.valor_total)}) no coincide con el neto del
        documento ({formatoPesos(doc.neto_documento)}). Puede haber un dígito mal leído o un producto sin valor.
      </p>
    )
  }
  return (
    <p className="verificacion revisar">
      ⚠ No se encontró el neto en el documento: no se pudo verificar la suma de los valores.
    </p>
  )
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
  const conValores = TIPOS_CON_VALORES.includes(resultado?.tipo)

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
            {resultado.codigo && <span className="codigo">{resultado.codigo}</span>}
            {resultado.tipo !== 'desconocido' && (
              <span className="confianza">{Math.round(resultado.confianza * 100)}% confianza</span>
            )}
          </h2>
          <p className="archivo">
            {resultado.archivo} ·{' '}
            <a href={resultado.url_archivo} target="_blank" rel="noreferrer">Abrir original</a>
          </p>

          {resultado.tipo !== 'desconocido' && !resultado.codigo && (
            <p className="verificacion revisar">⚠ No se encontró el número del documento.</p>
          )}

          {!esPdf && <img className="vista-previa" src={resultado.url_archivo} alt={resultado.archivo} />}

          <h3>Mercancías</h3>
          {resultado.items.length === 0 ? (
            <p className="vacio">No se encontró una tabla de ítems con columna de cantidad.</p>
          ) : (
            <table className="items">
              <thead>
                <tr>
                  <th>Descripción</th>
                  <th className="numero">Cantidad</th>
                  {conValores && <th className="numero">Valor total</th>}
                </tr>
              </thead>
              <tbody>
                {resultado.items.map((item, i) => (
                  <tr key={i}>
                    <td>{item.descripcion || '—'}</td>
                    <td className="numero">{formatoCantidad(item.cantidad)}</td>
                    {conValores && <td className="numero">{formatoPesos(item.total)}</td>}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th>Total ({resultado.items.length} ítems)</th>
                  <th className="numero">{formatoCantidad(resultado.cantidad_total)}</th>
                  {conValores && <th className="numero">{formatoPesos(resultado.valor_total)}</th>}
                </tr>
              </tfoot>
            </table>
          )}
          {conValores && resultado.items.length > 0 && <Verificacion doc={resultado} />}

          <h3>Clasificación</h3>
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
              <tr><th>Fecha</th><th>Archivo</th><th>Tipo</th><th>N° documento</th><th>Confianza</th><th className="numero">Cant. total</th><th className="numero">Valor total</th><th></th></tr>
            </thead>
            <tbody>
              {historial.map((doc) => (
                <tr key={doc.id} className={resultado?.id === doc.id ? 'ganador' : ''}>
                  <td>{new Date(doc.fecha_creacion + 'Z').toLocaleString('es-CL')}</td>
                  <td>
                    <button className="enlace" onClick={() => verDocumento(doc.id)}>{doc.archivo}</button>
                  </td>
                  <td>{doc.nombre}</td>
                  <td>{doc.codigo ?? '—'}</td>
                  <td>{doc.tipo === 'desconocido' ? '—' : `${Math.round(doc.confianza * 100)}%`}</td>
                  <td className="numero">{formatoCantidad(doc.cantidad_total)}</td>
                  <td className="numero">
                    {formatoPesos(doc.valor_total)}
                    {doc.valores_coinciden === false && (
                      <span className="alerta" title="La suma no coincide con el neto del documento: revisar"> ⚠</span>
                    )}
                  </td>
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
