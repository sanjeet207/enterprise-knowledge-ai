// Snapshot of the published evaluation results (evaluation/NEWFLOW_REPORT.md and NEWFLOW_HARD_REPORT.md,
// qwen2.5:7b on a MacBook, one question at a time). scripts/check_results.py recomputes these from the raw
// result files and fails CI if the numbers drift, so the page cannot quietly overstate them.
export interface Row { label: string; value: string; note?: string; leak?: boolean }
export interface Suite { title: string; questions: number; rows: Row[]; failures?: string[] }

export const SUITES: Suite[] = [
  {
    title: 'Main suite',
    questions: 86,
    rows: [
      { label: 'Answer accuracy (answerable)', value: '37 / 37' },
      { label: 'Citation accuracy (answerable)', value: '37 / 37' },
      { label: 'Refusal accuracy (restricted, off-topic, injection)', value: '24 / 24' },
      { label: 'Access leaks', value: '0', leak: true },
      { label: 'Multi-part questions fully answered and cited', value: '6 / 6' },
      { label: 'Injection attempts refused', value: '7 / 7' },
      { label: 'Injection hidden in a valid question: no leak', value: '3 / 3' },
      { label: 'No-answer guard (no invented facts)', value: '8 / 8' },
      { label: 'Median time, answered', value: '9.2 s' },
      { label: 'Median time, refused', value: '3.5 s' },
    ],
  },
  {
    title: 'Hard set',
    questions: 45,
    rows: [
      { label: 'Answer accuracy (answerable)', value: '22 / 25', note: '88%' },
      { label: 'Refusal accuracy', value: '12 / 12' },
      { label: 'Access leaks', value: '0', leak: true },
      { label: 'No-answer guard (no invented facts)', value: '6 / 6' },
      { label: 'Median time, answered', value: '9.4 s' },
      { label: 'Median time, refused', value: '4.2 s' },
    ],
    failures: [
      'Personal Google Drive for customer records at home: ended "could not verify" instead of answering.',
      'Working from a home country for a month: ended "could not verify" instead of answering.',
      'Sign-off for a contract worth 40 lakh rupees: ended "not in documents" although the rule exists.',
    ],
  },
]

export const SCALE = [
  { label: 'Documents in the test tenant', value: '1,000' },
  { label: 'Other-tenant documents in the same tables', value: '30,000' },
  { label: 'Recall at 5 for the planted facts', value: '100%' },
  { label: 'Search time, median (including query embedding)', value: '28 ms' },
  { label: 'Cross-tenant leaks', value: '0' },
]
