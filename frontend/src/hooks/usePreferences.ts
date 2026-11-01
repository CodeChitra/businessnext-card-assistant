import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null // storage can be blocked (private mode, policies); preferences are optional
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // ignore: the preference just won't persist
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Follows the OS until the user picks a theme; the choice is remembered per browser. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = read('theme')
    return saved === 'dark' || saved === 'light' ? saved : systemTheme()
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  const toggle = () =>
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      write('theme', next)
      return next
    })
  return { theme, toggle }
}

export function useInspector() {
  const [on, setOn] = useState(() => read('inspector') === 'on')
  const toggle = () =>
    setOn((v) => {
      write('inspector', v ? 'off' : 'on')
      return !v
    })
  return { on, toggle }
}
