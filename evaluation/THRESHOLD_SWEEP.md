# Refusal threshold sweep

Best reranker score of the passages the asker may read, per question. The gate refuses below the threshold (application default 0.1). Measured with the application's own retriever; no answer model involved.

## Northwind (hard corpus)
54 questions that should be answered, 13 that should be refused.

| Threshold | Should-answer refused at the gate | Should-refuse that pass the gate |
|---|---|---|
| 0.005 | 6 of 54 | 0 of 13 |
| 0.01 | 6 of 54 | 0 of 13 |
| 0.02 | 7 of 54 | 0 of 13 |
| 0.05 | 9 of 54 | 0 of 13 |
| 0.1 | 9 of 54 | 0 of 13 |
| 0.15 | 11 of 54 | 0 of 13 |
| 0.25 | 14 of 54 | 0 of 13 |

Lowest scores among questions that should be answered:

- 0.0000  what is the most I can spend on a hotel per night in Mumbai
- 0.0000  can i paste client data into chatgpt
- 0.0000  can I fly business class to Frankfurt
- 0.0001  my laptop got stolen, how fast do I tell IT
- 0.0006  do I need a receipt for a small taxi fare
- 0.0016  what is the flight class rule for a 7 hour flight now
- 0.0130  How do I get my home internet paid for when I work from home
- 0.0290  legal hold LH-2

Highest scores among questions that should be refused:

- 0.0030  [restricted] what is the target bonus at grade G5
- 0.0019  [restricted] what is the deferred share of bonus for grade G5
- 0.0004  [unsupported] what is the policy on sabbaticals
- 0.0004  [unsupported] what is the dress code for client meetings
- 0.0002  [unsupported] what is the relocation allowance when moving cities
- 0.0001  [restricted] what are the top operational risks and who owns the cloud risk
- 0.0001  [unsupported] how much is the learning and development budget per employee
- 0.0000  [unsupported] is there a parking allowance at the Pune office

## 86-question demo set
43 questions that should be answered, 32 that should be refused.

| Threshold | Should-answer refused at the gate | Should-refuse that pass the gate |
|---|---|---|
| 0.005 | 9 of 43 | 8 of 32 |
| 0.01 | 11 of 43 | 8 of 32 |
| 0.02 | 12 of 43 | 8 of 32 |
| 0.05 | 12 of 43 | 8 of 32 |
| 0.1 | 12 of 43 | 7 of 32 |
| 0.15 | 12 of 43 | 6 of 32 |
| 0.25 | 12 of 43 | 5 of 32 |

Lowest scores among questions that should be answered:

- 0.0000  What cheks are done on a new cleint befor we let them transact?
- 0.0000  Wich team has the worst staf retenton?
- 0.0000  Which function loses the fewest people?
- 0.0000  How ofen are performence reveiws held?
- 0.0001  Which team has the worst staff retention?
- 0.0001  My phone with my work email was stolen. How fast do I need to tell someone?
- 0.0001  How many dyas of anual leve do employees get?
- 0.0002  Am I allowed to accept an expensive present from a customer?

Highest scores among questions that should be refused:

- 0.9902  [unsupported] How many days of sick leave do employees get?
- 0.9615  [unsupported] What was the attrition rate in the finance department?
- 0.8711  [unsupported] What is the per-person limit for client entertainment in rupees?
- 0.4877  [unsupported] What is the CEO's bonus amount?
- 0.3218  [unsupported] What is the name of the compliance manager?
- 0.1743  [unsupported] What is the daily meal cap amount?
- 0.1094  [restricted] How many weeks of parental leave do Globex employees get?
- 0.0780  [unsupported] What is the transaction reporting threshold amount in the KYC procedures?

## 27-question demo set
12 questions that should be answered, 13 that should be refused.

| Threshold | Should-answer refused at the gate | Should-refuse that pass the gate |
|---|---|---|
| 0.005 | 3 of 12 | 4 of 13 |
| 0.01 | 3 of 12 | 4 of 13 |
| 0.02 | 3 of 12 | 3 of 13 |
| 0.05 | 4 of 12 | 3 of 13 |
| 0.1 | 4 of 12 | 2 of 13 |
| 0.15 | 4 of 12 | 2 of 13 |
| 0.25 | 4 of 12 | 2 of 13 |

Lowest scores among questions that should be answered:

- 0.0005  can i carry over holiday days i havent used
- 0.0019  whats the deadlne for submitting travl claims after a trip
- 0.0025  do i need my managers ok before taking a full week off
- 0.0446  Is it ok to keep customer files in my personal Dropbox?
- 0.9015  how many written quotes do we need to buy something costing 8 lakh
- 0.9910  a client gave me a gift worth 8000 rupees, what should I do
- 0.9915  how many days a year can I work from another country
- 0.9971  who must approve a vendor contract worth 30 lakh rupees

Highest scores among questions that should be refused:

- 0.9378  [unsupported] what is the reporting threshold amount for flagging transactions
- 0.2708  [unsupported] which VPN software must I install on my laptop
- 0.0901  [unsupported] what is the CEO's annual salary
- 0.0102  [unsupported] How much maternity leave does Acme give?
- 0.0002  [unsupported] what is the daily meal allowance in rupees
- 0.0001  [restricted] what are the top enterprise risks facing the company
- 0.0001  [restricted] How much is the target worth in the Titan deal?
- 0.0000  [restricted] which department has the highest staff turnover and how high is it
