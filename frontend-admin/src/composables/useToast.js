import { reactive, inject, provide } from 'vue'

const TOAST_KEY = Symbol('toast')

export function createToast() {
  const toasts = reactive([])
  let id = 0

  const add = (type, message, duration = 3000) => {
    const toast = { id: ++id, type, message }
    toasts.push(toast)
    setTimeout(() => {
      const idx = toasts.findIndex(t => t.id === toast.id)
      if (idx > -1) toasts.splice(idx, 1)
    }, duration)
  }

  const toast = {
    toasts,
    success: (msg) => add('success', msg),
    error: (msg) => add('error', msg),
    warning: (msg) => add('warning', msg),
    info: (msg) => add('info', msg)
  }

  return toast
}

export function provideToast() {
  const toast = createToast()
  provide(TOAST_KEY, toast)
  return toast
}

export function useToast() {
  return inject(TOAST_KEY)
}
