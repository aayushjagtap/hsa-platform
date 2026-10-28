// Money crosses the API as integer cents. Converting user input with
// parseFloat(x) * 100 can be off by a cent (e.g. 19.99 * 100 = 1998.9999...),
// so dollars are parsed as a string instead.

const DOLLARS = /^\d{1,7}(\.\d{1,2})?$/

export function parseDollarsToCents(input: string): number | null {
  const value = input.trim().replace(/[$,]/g, '')
  if (!DOLLARS.test(value)) return null
  const [whole, fraction = ''] = value.split('.')
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  return cents > 0 ? cents : null
}

const formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function formatCents(cents: number): string {
  return formatter.format(cents / 100)
}
