// Diálogos con SweetAlert2 en lugar de confirm() / prompt() del navegador, con el estilo del dashboard.
import Swal from 'sweetalert2'

const BOTON = 'inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium shadow-sm transition'

const CLASES = {
  popup: 'rounded-2xl font-sans',
  title: 'text-lg font-semibold text-slate-900',
  htmlContainer: 'text-sm text-slate-600',
  actions: 'gap-2',
  confirmButton: `${BOTON} bg-slate-900 text-white hover:bg-slate-800`,
  cancelButton: `${BOTON} bg-white text-slate-700 ring-1 ring-inset ring-slate-200 hover:bg-slate-50`,
  input: 'rounded-lg border-0 text-sm text-slate-900 ring-1 ring-inset ring-slate-200 focus:ring-2 focus:ring-indigo-500',
}

const dialogo = Swal.mixin({
  buttonsStyling: false,
  reverseButtons: true, // Cancelar a la izquierda, la acción a la derecha
  focusCancel: true,
  cancelButtonText: 'Cancelar',
  customClass: CLASES,
})

/** Pide confirmación. `peligro`: la acción borra algo (botón rojo). Devuelve true si se confirmó. */
export async function confirmar({ titulo, texto, boton = 'Confirmar', peligro = false }) {
  const { isConfirmed } = await dialogo.fire({
    icon: peligro ? 'warning' : 'question',
    title: titulo,
    text: texto,
    showCancelButton: true,
    confirmButtonText: boton,
    customClass: peligro ? { ...CLASES, confirmButton: `${BOTON} bg-rose-600 text-white hover:bg-rose-500` } : CLASES,
  })
  return isConfirmed
}

/** Pide un texto opcional. Devuelve el texto (puede ser vacío) o null si se canceló. */
export async function pedirTexto({ titulo, texto, etiqueta, valor = '', boton = 'Aceptar' }) {
  const { isConfirmed, value } = await dialogo.fire({
    icon: 'question',
    title: titulo,
    text: texto,
    input: 'text',
    inputLabel: etiqueta,
    inputValue: valor,
    inputAttributes: { maxlength: '255' },
    showCancelButton: true,
    confirmButtonText: boton,
    focusCancel: false,
  })
  return isConfirmed ? value : null
}

/** Muestra un error. */
export function mostrarError(texto) {
  return dialogo.fire({ icon: 'error', title: 'No se pudo completar la acción', text: texto, confirmButtonText: 'Entendido' })
}
