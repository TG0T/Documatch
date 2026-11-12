import { useMemo, useState } from 'react'
import { Icon } from './iconos.jsx'

/* ══════════════════════════════════════════════════════════════
   VISOR DE INDICADORES (KPI)
   Se calcula con las mismas filas del dashboard (/api/dashboard): una por orden de compra con
   sus guías y facturas.
   ══════════════════════════════════════════════════════════════ */

// Colores de estado (reservados: siempre van con ícono y texto, nunca solos)
const ESTADOS = [
  { clave: 'ok',           texto: 'Conciliadas',      color: '#0ca30c', icono: 'check' },
  { clave: 'parcial',      texto: 'Despacho parcial', color: '#fab219', icono: 'clock' },
  { clave: 'discrepancia', texto: 'Discrepancias',    color: '#d03b3b', icono: 'alert' },
  { clave: 'pendiente',    texto: 'Pendientes',       color: '#2a78d6', icono: 'truck' },
  { clave: 'finalizada',   texto: 'Finalizadas',      color: '#898781', icono: 'check' },
]

// Series de "pedido / recibido / facturado" (paleta categórica validada, en orden fijo)
const SERIES = [
  { clave: 'pedido',     texto: 'Pedido (OC)',      color: '#2a78d6' },
  { clave: 'despachado', texto: 'Recibido (guías)', color: '#eb6834' },
  { clave: 'facturado',  texto: 'Facturado',        color: '#1baf7a' },
]

const MAX_ORDENES_GRAFICO = 8
const MESES_GRAFICO = 12

const numero = (n) => (n == null ? '—' : n.toLocaleString('es-CL', { maximumFractionDigits: 1 }))
const compacto = (n) => new Intl.NumberFormat('es-CL', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
const pesos = (n) => (n == null ? '—' : `$${compacto(n)}`)
const pesosCompletos = (n) => (n == null ? '—' : `$${n.toLocaleString('es-CL', { maximumFractionDigits: 0 })}`)
const porcentaje = (n) => (n == null ? '—' : `${Math.round(n * 100)}%`)
const sumar = (valores) => valores.reduce((s, v) => s + (v ?? 0), 0)
const nombreMes = (clave) => {
  const [anio, mes] = clave.split('-').map(Number)
  return new Date(anio, mes - 1, 1).toLocaleDateString('es-CL', { month: 'short', year: '2-digit' })
}

// Eje con números redondos (0, 5, 10, 15...) y unas 4 divisiones
function escala(maximo) {
  if (!maximo || maximo <= 0) return { tope: 1, marcas: [0, 1] }
  const crudo = maximo / 4
  const magnitud = 10 ** Math.floor(Math.log10(crudo))
  const paso = [1, 2, 2.5, 5, 10].map((m) => m * magnitud).find((p) => p >= crudo)
  const tope = Math.ceil(maximo / paso) * paso
  const marcas = []
  for (let v = 0; v <= tope + paso / 2; v += paso) marcas.push(Math.round(v * 100) / 100)
  return { tope, marcas }
}

/* ══════════════════════════════════════════════════════════════
   CÁLCULO DE INDICADORES
   ══════════════════════════════════════════════════════════════ */

function calcular(filas) {
  const total = filas.length
  const porEstado = Object.fromEntries(ESTADOS.map((e) => [e.clave, filas.filter((f) => f.estado === e.clave).length]))
  const alDia = porEstado.ok + porEstado.finalizada

  const comprometido = sumar(filas.map((f) => f.orden.valor_total))
  const facturado = sumar(filas.flatMap((f) => f.facturas.map((x) => x.valor_total)))

  // Cumplimiento de despacho: unidades recibidas sobre las pedidas, en las OC que ya tienen guía
  // (lo recibido de más no compensa lo que falta en otra orden)
  const conGuia = filas.filter((f) => f.pedido > 0 && f.despachado != null)
  const pedidoConGuia = sumar(conGuia.map((f) => f.pedido))
  const cumplimiento = pedidoConGuia ? sumar(conGuia.map((f) => Math.min(f.despachado, f.pedido))) / pedidoConGuia : null

  const discrepancias = filas.filter((f) => f.estado === 'discrepancia')

  // Calidad de lectura del OCR, sobre todos los documentos del dashboard
  const documentos = filas.flatMap((f) => [f.orden, ...f.guias, ...f.facturas])
  const conValores = documentos.filter((d) => d.tipo !== 'guia_despacho' && d.items.length > 0)

  // Órdenes cargadas por mes (incluye los meses sin órdenes entre la primera y la última)
  const porMes = {}
  for (const f of filas) {
    if (f.orden.fecha) {
      const clave = f.orden.fecha.slice(0, 7)
      porMes[clave] = (porMes[clave] ?? 0) + 1
    }
  }
  const claves = Object.keys(porMes).sort()
  const meses = []
  if (claves.length) {
    let [anio, mes] = claves[0].split('-').map(Number)
    const ultima = claves[claves.length - 1]
    for (;;) {
      const clave = `${anio}-${String(mes).padStart(2, '0')}`
      meses.push({ clave, cantidad: porMes[clave] ?? 0 })
      if (clave >= ultima) break
      mes += 1
      if (mes > 12) { mes = 1; anio += 1 }
    }
  }

  // Órdenes con más unidades pedidas, para comparar pedido / recibido / facturado
  const comparacion = filas
    .filter((f) => f.pedido != null)
    .sort((a, b) => b.pedido - a.pedido)
    .slice(0, MAX_ORDENES_GRAFICO)
    .map((f) => ({ codigo: f.orden.codigo ?? '(sin número)', pedido: f.pedido, despachado: f.despachado, facturado: f.facturado }))

  // Órdenes que requieren atención: primero las discrepancias, después los despachos con menor avance
  const atencion = filas
    .filter((f) => f.estado === 'discrepancia' || f.estado === 'parcial')
    .sort((a, b) => (a.estado === b.estado ? (a.avance ?? 0) - (b.avance ?? 0) : a.estado === 'discrepancia' ? -1 : 1))

  return {
    total,
    porEstado,
    alDia,
    tasaAlDia: total ? alDia / total : null,
    comprometido,
    facturado,
    ordenesConMonto: filas.filter((f) => f.orden.valor_total != null).length,
    cumplimiento,
    ordenesConGuia: conGuia.length,
    discrepancias: discrepancias.length,
    montoEnDiscrepancia: sumar(discrepancias.map((f) => f.orden.valor_total)),
    documentos: documentos.length,
    confianza: documentos.length ? sumar(documentos.map((d) => d.confianza)) / documentos.length : null,
    verificados: conValores.filter((d) => d.valores_coinciden === true).length,
    verificables: conValores.length,
    corregidos: documentos.filter((d) => d.cantidades_editadas).length,
    sinNumero: documentos.filter((d) => !d.codigo).length,
    meses: meses.slice(-MESES_GRAFICO),
    comparacion,
    atencion,
  }
}

/* ══════════════════════════════════════════════════════════════
   PIEZAS
   ══════════════════════════════════════════════════════════════ */

function Tarjeta({ titulo, descripcion, accion, children, className = '' }) {
  return (
    <section className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{titulo}</h2>
          {descripcion && <p className="mt-0.5 text-xs text-slate-500">{descripcion}</p>}
        </div>
        {accion}
      </div>
      {children}
    </section>
  )
}

function Indicador({ etiqueta, valor, detalle, icono }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
        <Icon name={icono} className="h-4 w-4 text-slate-400" />
        {etiqueta}
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{valor}</p>
      {detalle && <p className="mt-1.5 text-xs text-slate-500">{detalle}</p>}
    </div>
  )
}

// Recuadro que sigue al mouse sobre un gráfico
function useTooltip() {
  const [tip, setTip] = useState(null)
  const mostrar = (contenido) => (e) => {
    const caja = e.currentTarget.closest('[data-grafico]').getBoundingClientRect()
    setTip({ contenido, x: e.clientX - caja.left, y: e.clientY - caja.top })
  }
  const ocultar = () => setTip(null)
  const elemento = tip && (
    <div className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-slate-900 px-3 py-2 text-xs text-white shadow-lg"
         style={{ left: tip.x, top: tip.y - 10 }}>
      {tip.contenido}
    </div>
  )
  return { mostrar, ocultar, elemento }
}

function Leyenda({ series }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
      {series.map((s) => (
        <span key={s.clave} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
          {s.texto}
        </span>
      ))}
    </div>
  )
}

// Ejes y líneas de referencia de un gráfico de columnas; las columnas van en `children`
function Columnas({ marcas, tope, alto = 200, etiquetas, children }) {
  return (
    // pt-3: espacio para la marca superior del eje, que se centra sobre su línea
    <div className="flex gap-2 pt-3">
      <div className="relative w-10 shrink-0 text-right text-[11px] tabular-nums text-slate-400" style={{ height: alto }}>
        {marcas.map((m) => (
          <span key={m} className="absolute right-0 -translate-y-1/2" style={{ bottom: `${(m / tope) * 100}%` }}>
            {compacto(m)}
          </span>
        ))}
      </div>
      <div className="min-w-0 flex-1">
        <div className="relative" style={{ height: alto }}>
          {marcas.map((m) => (
            <div key={m} className={`absolute inset-x-0 h-px ${m === 0 ? 'bg-slate-300' : 'bg-slate-100'}`}
                 style={{ bottom: `${(m / tope) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end justify-around">{children}</div>
        </div>
        <div className="mt-2 flex justify-around">{etiquetas}</div>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   GRÁFICOS
   ══════════════════════════════════════════════════════════════ */

function GraficoEstados({ porEstado, total }) {
  const { mostrar, ocultar, elemento } = useTooltip()
  const maximo = Math.max(...Object.values(porEstado), 1)
  return (
    <div className="relative space-y-3" data-grafico>
      {ESTADOS.map((e) => {
        const cantidad = porEstado[e.clave]
        return (
          <div key={e.clave} className="flex items-center gap-3"
               onMouseMove={mostrar(<><b>{e.texto}</b>: {cantidad} de {total} órdenes ({porcentaje(total ? cantidad / total : 0)})</>)}
               onMouseLeave={ocultar}>
            <span className="flex w-36 shrink-0 items-center gap-1.5 text-sm text-slate-600">
              <Icon name={e.icono} className="h-4 w-4 text-slate-400" />
              {e.texto}
            </span>
            <div className="flex h-5 flex-1 items-center">
              {cantidad > 0 && (
                <div className="h-5 rounded-r" style={{ width: `${(cantidad / maximo) * 100}%`, background: e.color }} />
              )}
              <span className="ml-2 text-sm font-medium tabular-nums text-slate-900">{cantidad}</span>
            </div>
          </div>
        )
      })}
      {elemento}
    </div>
  )
}

function GraficoComparacion({ datos }) {
  const { mostrar, ocultar, elemento } = useTooltip()
  const { tope, marcas } = escala(Math.max(...datos.flatMap((d) => SERIES.map((s) => d[s.clave] ?? 0))))
  return (
    <div className="relative" data-grafico>
      <Columnas marcas={marcas} tope={tope}
        etiquetas={datos.map((d) => (
          <span key={d.codigo} title={d.codigo} className="w-0 flex-1 truncate px-1 text-center text-[11px] text-slate-500">{d.codigo}</span>
        ))}>
        {datos.map((d) => (
          <div key={d.codigo} className="flex h-full flex-1 items-end justify-center gap-0.5"
               onMouseMove={mostrar(
                 <div className="space-y-0.5">
                   <p className="font-semibold">{d.codigo}</p>
                   {SERIES.map((s) => (
                     <p key={s.clave} className="flex items-center gap-1.5">
                       <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
                       {s.texto}: <b className="tabular-nums">{numero(d[s.clave])}</b>
                     </p>
                   ))}
                 </div>,
               )}
               onMouseLeave={ocultar}>
            {SERIES.map((s) => (
              <div key={s.clave} className="w-3.5 rounded-t sm:w-4"
                   style={{ height: `${((d[s.clave] ?? 0) / tope) * 100}%`, background: s.color }} />
            ))}
          </div>
        ))}
      </Columnas>
      {elemento}
    </div>
  )
}

function TablaComparacion({ datos }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
          <tr className="border-b border-slate-200">
            <th className="py-2 pr-3 font-semibold">Orden de compra</th>
            {SERIES.map((s) => <th key={s.clave} className="py-2 pl-3 text-right font-semibold">{s.texto}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 tabular-nums">
          {datos.map((d) => (
            <tr key={d.codigo}>
              <td className="py-2 pr-3 font-medium text-slate-900">{d.codigo}</td>
              {SERIES.map((s) => <td key={s.clave} className="py-2 pl-3 text-right text-slate-700">{numero(d[s.clave])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function GraficoMeses({ meses }) {
  const { mostrar, ocultar, elemento } = useTooltip()
  const { tope, marcas } = escala(Math.max(...meses.map((m) => m.cantidad)))
  const ultimo = meses[meses.length - 1]
  return (
    <div className="relative" data-grafico>
      <Columnas marcas={marcas} tope={tope} alto={170}
        etiquetas={meses.map((m) => (
          <span key={m.clave} className="w-0 flex-1 truncate text-center text-[11px] text-slate-500">{nombreMes(m.clave)}</span>
        ))}>
        {meses.map((m) => (
          <div key={m.clave} className="flex h-full flex-1 flex-col items-center justify-end"
               onMouseMove={mostrar(<><b>{nombreMes(m.clave)}</b>: {m.cantidad} {m.cantidad === 1 ? 'orden' : 'órdenes'}</>)}
               onMouseLeave={ocultar}>
            {/* Solo el último mes lleva su valor escrito; el resto se lee en el eje y el tooltip */}
            {m === ultimo && <span className="mb-1 text-xs font-medium tabular-nums text-slate-900">{m.cantidad}</span>}
            <div className="w-5 rounded-t sm:w-6" style={{ height: `${(m.cantidad / tope) * 100}%`, background: '#2a78d6' }} />
          </div>
        ))}
      </Columnas>
      {elemento}
    </div>
  )
}

function Medidor({ fraccion }) {
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full" style={{ background: '#d7f0d7' }}>
      <div className="h-full rounded-full" style={{ width: `${Math.round((fraccion ?? 0) * 100)}%`, background: '#0ca30c' }} />
    </div>
  )
}

/* ══════════════════════════════════════════════════════════════
   VISTA
   ══════════════════════════════════════════════════════════════ */

export default function Indicadores({ filas, recargar, irAlDashboard }) {
  const k = useMemo(() => calcular(filas), [filas])
  const [verTabla, setVerTabla] = useState(false)

  const encabezado = (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Indicadores</h1>
        <p className="mt-1 text-sm text-slate-500">
          Calculados con las {k.total} órdenes de compra del dashboard y sus guías y facturas.
        </p>
      </div>
      <button onClick={recargar}
        className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-inset ring-slate-200 transition hover:bg-slate-50">
        <Icon name="refresh" /> Actualizar
      </button>
    </div>
  )

  if (k.total === 0) {
    return (
      <div className="space-y-6">
        {encabezado}
        <div className="rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center shadow-sm">
          <Icon name="chart" className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-2 text-sm font-medium text-slate-700">Aún no hay órdenes de compra</p>
          <p className="mt-1 text-xs text-slate-500">Carga una OC en el dashboard para ver los indicadores.</p>
          <button onClick={irAlDashboard}
            className="mt-4 rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-800">
            Ir al dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {encabezado}

      {/* Indicador principal y montos */}
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:col-span-2 xl:col-span-1 xl:row-span-2">
          <p className="text-sm font-medium text-slate-500">Órdenes al día</p>
          <p className="mt-3 text-5xl font-semibold tracking-tight text-slate-900">{porcentaje(k.tasaAlDia)}</p>
          <div className="mt-4"><Medidor fraccion={k.tasaAlDia} /></div>
          <p className="mt-3 text-xs text-slate-500">
            {k.alDia} de {k.total} órdenes conciliadas o finalizadas.
          </p>
          <dl className="mt-5 space-y-2 border-t border-slate-100 pt-4 text-sm">
            {ESTADOS.filter((e) => e.clave !== 'ok' && e.clave !== 'finalizada').map((e) => (
              <div key={e.clave} className="flex items-center justify-between">
                <dt className="flex items-center gap-1.5 text-slate-600">
                  <span className="h-2 w-2 rounded-full" style={{ background: e.color }} />
                  {e.texto}
                </dt>
                <dd className="font-medium tabular-nums text-slate-900">{k.porEstado[e.clave]}</dd>
              </div>
            ))}
          </dl>
        </div>
        <Indicador etiqueta="Monto comprometido" icono="box" valor={pesos(k.comprometido)}
          detalle={`${pesosCompletos(k.comprometido)} en ${k.ordenesConMonto} de ${k.total} OC con valores`} />
        <Indicador etiqueta="Monto facturado" icono="doc" valor={pesos(k.facturado)}
          detalle={k.comprometido ? `${porcentaje(k.facturado / k.comprometido)} del monto comprometido` : 'Sin montos en las OC'} />
        <Indicador etiqueta="Cumplimiento de despacho" icono="truck" valor={porcentaje(k.cumplimiento)}
          detalle={k.ordenesConGuia
            ? `Unidades recibidas sobre las pedidas, en ${k.ordenesConGuia} OC con guía`
            : 'Ninguna OC tiene guías de despacho aún'} />
        <Indicador etiqueta="Discrepancias abiertas" icono="alert" valor={k.discrepancias}
          detalle={k.discrepancias ? `${pesos(k.montoEnDiscrepancia)} en órdenes con diferencias` : 'Sin diferencias entre documentos'} />
        <Indicador etiqueta="Lectura verificada" icono="check"
          valor={k.verificables ? porcentaje(k.verificados / k.verificables) : '—'}
          detalle={`${k.verificados} de ${k.verificables} OC y facturas cuadran con su neto`} />
        <Indicador etiqueta="Confianza del OCR" icono="search" valor={porcentaje(k.confianza)}
          detalle={`Promedio de ${k.documentos} documentos · ${k.corregidos} corregidos a mano`} />
      </section>

      {/* Estados y comparación de cantidades */}
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <Tarjeta titulo="Estado de las órdenes" descripcion="Cantidad de órdenes de compra por estado" className="xl:col-span-2">
          <GraficoEstados porEstado={k.porEstado} total={k.total} />
        </Tarjeta>
        <Tarjeta titulo="Pedido, recibido y facturado"
          descripcion={`Unidades por orden · las ${k.comparacion.length} OC con más unidades pedidas`}
          className="xl:col-span-3"
          accion={
            <button onClick={() => setVerTabla((v) => !v)}
              className="shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
              {verTabla ? 'Ver gráfico' : 'Ver tabla'}
            </button>
          }>
          {k.comparacion.length === 0 ? (
            <p className="py-10 text-center text-xs italic text-slate-400">Ninguna OC tiene cantidades legibles</p>
          ) : verTabla ? (
            <TablaComparacion datos={k.comparacion} />
          ) : (
            <div className="space-y-4">
              <Leyenda series={SERIES} />
              <GraficoComparacion datos={k.comparacion} />
            </div>
          )}
        </Tarjeta>
      </section>

      {/* Evolución y calidad */}
      <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <Tarjeta titulo="Órdenes cargadas por mes" descripcion={k.meses.length === 1 ? 'Último mes con actividad' : `Últimos ${k.meses.length} meses con actividad`} className="xl:col-span-3">
          {k.meses.length === 0
            ? <p className="py-10 text-center text-xs italic text-slate-400">Sin fechas registradas</p>
            : <GraficoMeses meses={k.meses} />}
        </Tarjeta>
        <Tarjeta titulo="Calidad de la lectura" descripcion="Qué tanto hay que revisar a mano" className="xl:col-span-2">
          <dl className="divide-y divide-slate-100 text-sm">
            {[
              ['Documentos procesados', numero(k.documentos)],
              ['Confianza promedio del OCR', porcentaje(k.confianza)],
              ['OC y facturas que cuadran con su neto', `${k.verificados} de ${k.verificables}`],
              ['Documentos con cantidades corregidas', numero(k.corregidos)],
              ['Documentos sin número legible', numero(k.sinNumero)],
            ].map(([etiqueta, valor]) => (
              <div key={etiqueta} className="flex items-center justify-between gap-3 py-2.5">
                <dt className="text-slate-600">{etiqueta}</dt>
                <dd className="font-medium tabular-nums text-slate-900">{valor}</dd>
              </div>
            ))}
          </dl>
        </Tarjeta>
      </section>

      {/* Órdenes que requieren atención */}
      <Tarjeta titulo="Órdenes que requieren atención"
        descripcion="Discrepancias primero; después los despachos parciales con menor avance"
        accion={
          <button onClick={irAlDashboard}
            className="shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-50">
            Ir al dashboard
          </button>
        }>
        {k.atencion.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            <Icon name="check" className="mr-1 inline h-4 w-4 text-slate-400" />
            No hay órdenes con discrepancias ni despachos parciales.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                <tr className="whitespace-nowrap border-b border-slate-200">
                  <th className="py-2 pr-3 font-semibold">Orden de compra</th>
                  <th className="px-3 py-2 font-semibold">Estado</th>
                  <th className="px-3 py-2 text-right font-semibold">Avance</th>
                  <th className="px-3 py-2 text-right font-semibold">Por recibir</th>
                  <th className="px-3 py-2 text-right font-semibold">Monto OC</th>
                  <th className="py-2 pl-3 font-semibold">Detalle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {k.atencion.map((f) => {
                  const estado = ESTADOS.find((e) => e.clave === f.estado)
                  const porRecibir = f.pedido != null && f.despachado != null ? Math.max(f.pedido - f.despachado, 0) : null
                  return (
                    <tr key={f.orden.id}>
                      <td className="whitespace-nowrap py-2.5 pr-3 font-medium text-slate-900">{f.orden.codigo ?? '(sin número)'}</td>
                      <td className="whitespace-nowrap px-3 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-slate-700">
                          <span className="h-2 w-2 rounded-full" style={{ background: estado.color }} />
                          <Icon name={estado.icono} className="h-3.5 w-3.5 text-slate-400" />
                          {estado.texto}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{f.avance == null ? '—' : `${f.avance}%`}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{numero(porRecibir)}</td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{pesosCompletos(f.orden.valor_total)}</td>
                      <td className="py-2.5 pl-3 text-xs text-slate-500">{f.detalle}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>
    </div>
  )
}
