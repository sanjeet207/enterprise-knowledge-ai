import { useEffect } from 'react'

/** Runs an async loader when the page opens (and again if the loader itself changes). */
export function useLoad(load: () => Promise<void>): void {
  useEffect(() => { void load() }, [load])
}
