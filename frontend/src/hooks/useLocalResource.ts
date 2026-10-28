import { useCallback, useEffect, useState } from 'react'

type ResourceState<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string }

export function useLocalResource<T>(load: () => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: 'loading' })

  const reload = useCallback(() => {
    setState({ status: 'loading' })
    void load()
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : 'The local request failed.'
        setState({ status: 'error', message })
      })
  }, [load])

  useEffect(() => {
    reload()
  }, [reload])

  return { state, reload }
}
