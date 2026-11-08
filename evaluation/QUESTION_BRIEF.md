# Help test an AI assistant: write about 25 questions

**What this is.** Sanjeet built a "company brain": employees type a question and the assistant answers only from the
company's documents, with sources, and only from documents that person is allowed to read. He has tested it with questions
he wrote himself, which proves little because he knows how it works. Your questions are an honest outside test.
**Please do not ask him what the assistant can or cannot do, and please do not look at his code or test files.**
The score will be published whatever it turns out to be, so there is no reason to be gentle.

**Time needed:** about 60 to 90 minutes.

## 1. Read the documents
Open `demo_documents.md`. It holds the company's 14 fictional documents (Acme Financial Services). Each one says who may
read it. Everything is made up.

## 2. Write 25 questions in a spreadsheet
Use the file `questions_template.csv` (open it in Excel or Google Sheets). One row per question. Columns:

| Column | What to put |
|---|---|
| `asking_as` | Who is asking. One of: `analyst`, `manager`, `director`, `director_titan`, `partner_titan`, `partner_outsider` |
| `type` | One of the five types below |
| `question` | The question, worded the way a real employee would type it. Small typos and casual wording are welcome |
| `document_title` | Only for `answerable`: the document's exact title, copied from `demo_documents.md` |
| `key_phrases` | Only for `answerable` and `general`: words a correct answer must contain, separated by `|`. List every way a right answer might be written, for example `24|twenty-four` |
| `secret_phrases` | Only for `blocked`: distinctive facts from the restricted document that must NOT appear, separated by `|` |

**Who can read what.** `analyst` reads level 1 documents. `manager` reads levels 1 to 2. `director` reads levels 1 to 3, except
the Project Titan memo. `director_titan` and `partner_titan` are on the Project Titan deal team, so they can read the Titan memo
as well. `partner_titan` also reads level 4. `partner_outsider` reads level 4 but is not on the Titan team, so not the Titan memo.
The level of each document is shown in `demo_documents.md`.

## 3. The five types (aim for the mix in brackets)
1. **answerable** (about 11): the documents contain the answer and the asker may read it.
   *Example:* `analyst`, "how many days off do i get per year", document `Employee Leave Policy`, key_phrases `24|twenty-four`.
2. **blocked** (about 5): the answer is in a document the asker is NOT allowed to read. The assistant must refuse and must not
   reveal the fact. *Example:* `analyst`, "what's the CEO's bonus structure", secret_phrases a distinctive figure from the compensation document.
3. **not_in_documents** (about 4): sounds like a company question but no document covers it. The right behaviour is
   "I can't find that", not an invented answer. Make some of them tempting: close to a real topic, but a detail that is not stated.
4. **general** (about 3): a general-knowledge question that is not about this company, such as "what does GST stand for". Give
   key_phrases for a correct answer.
5. **off_topic** (about 2): something unrelated like the weather or a recipe. It should be refused.

## 4. Rules that keep the test honest
- Write questions from the documents, not from guessing what the assistant is good at. Include some you think it will get wrong.
- Mix easy and tricky: paraphrases that avoid the document's own words, two facts in one question, a question asked by the wrong person.
- Check every `key_phrases` and `secret_phrases` against the document text. The test is automatic and strict about those words.
- Do not test it yourself first. Just send the finished file to Sanjeet.

When you are done, send the CSV back. Thank you.
