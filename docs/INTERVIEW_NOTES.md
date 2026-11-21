# Interview notes

A short guide for explaining this project in an interview. Every number here comes from the reports in `evaluation/`;
where something is not measured, it says so.

## 30-second pitch

An internal "company brain". Employees ask questions in plain language and get answers only from their company's own
documents, with citations, and only from documents they are allowed to see. Off-topic questions are refused, and every
question is written to an audit log.

## What I would point to

- **Access control is in the database query, not in the prompt.** Tenant, classification level and engagement
  membership are filtered in SQL before anything reaches the model, so the model cannot leak what it never receives.
  Result: 0 access leaks on the 86-question suite and on the 45-question hard set.
- **Answers are checked, not trusted.** The pipeline has a relevance gate, a refusal path, checks on numbers and fit,
  and a validator with retries. See the README for the full flow.
- **It is measured.** 86-question suite: 100%, 0 leaks. 45-question hard set: 88% on its 25 answerable questions (22 of 25), 0 leaks, with the three misses listed.
- **The model is a setting.** Local Ollama by default; Anthropic, Groq or an OpenAI-compatible endpoint with one
  environment variable. 344 unit tests cover the provider code with a faked HTTP layer.

## Honest limits (say these before they are asked)

- The evaluation numbers were measured on the **local model only**. No hosted-model evaluation exists yet.
- The question sets were written by me, so they are not independent. An independent set is planned and will be
  published unchanged.
- The Azure deployment guide is **written, not yet deployed** to a real subscription.
- Hosted providers receive the question and the retrieved passages, so data leaves the deployment (see the threat model).
- Latency figures are not like-for-like across runs because the pipeline changed between them.

## Likely questions

1. *Why filter in SQL instead of telling the model what it may see?* A prompt is advice; a query is enforcement.
2. *How do you know it is correct?* Evaluation suites with named misses, plus an unrelated check on every answer.
3. *What would you do with more time?* Independent question set, hosted-model evaluation, live deployment with SSO.
4. *What went wrong?* Tests passed in one environment and failed on another because a developer `.env` changed routing;
   fixed by clearing model variables in the test fixture. A good story about test isolation.
