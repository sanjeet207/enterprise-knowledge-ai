export function fmtDate(value?: string | null): string {
  return value ? new Date(value).toLocaleDateString() : ''
}
export function fmtDateTime(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : ''
}
