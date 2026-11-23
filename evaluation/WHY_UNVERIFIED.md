# Why drafts were not shown (Northwind, latest run per question)

14 questions. Validator and answer steps from the audit trace.

## [no_answer] How many days of leave do UK employees get and how long can I work abroad in a year?  (asked by analyst, best score 0.993)
- refiner: search with: How many days of leave are UK employees entitled to, and how long can an employee work abroad in a year according to the company's policy? (score 0.977 -> 0.993)
- analysis: depth standard, format short
- answerer: drafted: UK employees receive 25 days of paid annual leave plus 8 public holidays [1]. The documents do not provide information on how long employees can work abroad in a year [2][3][1].
- validator: UNSUPPORTED citation mismatch: The documents do not provide information on how long employees can work abroad in a year [2][3][1].
- answerer: retry: grounding: INSUFFICIENT_INFORMATION [1] [2] [3]
- answerer: insufficient

## [no_answer] MLRO  (asked by manager, best score 0.229)
- refiner: search with: What are the responsibilities and procedures for an MLRO as outlined in the official policy? (score 0.229 -> 0.229)
- analysis: depth quick, format short
- answerer: insufficient

## [no_answer] NorthTrip  (asked by analyst, best score 0.879)
- refiner: search with: What is the policy regarding North Trip? (score 0.436 -> 0.879)
- analysis: depth quick, format short
- answerer: insufficient

## [no_answer] can i paste client data into chatgpt  (asked by analyst, best score 0.149)
- refiner: search with: Is it permissible to paste client data into ChatGPT? (score 0.000 -> 0.000)
- analysis: depth quick, format short
- answerer: insufficient

## [no_answer] do I need a receipt for a small taxi fare  (asked by analyst, best score 0.706)
- refiner: no change
- analysis: depth standard, format short
- answerer: insufficient

## [unverified] at what trip cost does a director need to approve before booking  (asked by analyst, best score 0.999)
- refiner: search with: At what trip cost does a director need to approve a booking? (score 0.999 -> 0.999)
- analysis: depth standard, format short
- answerer: drafted: A trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked [2, 3].
- answerer: retry: citations
- validator: uncited: Since both documents provide conflicting information, the most recent document (2025) should be considered authoritative.
- answerer: retry: citations: According to the 2025 Travel and Expense Policy [3], a trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked.
- validator: UNSUPPORTED According to the 2025 Travel and Expense Policy [3], a trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked.
- answerer: retry: grounding: According to the Travel and Expense Policy 2025 [3], a trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked.
- validator: UNSUPPORTED According to the Travel and Expense Policy 2025 [3], a trip with an estimated cost above INR 150,000 needs the approval of a director before it is booked.

## [unverified] how many days of annual leave do I get  (asked by analyst, best score 0.758)
- refiner: search with: How many days of annual leave am I entitled to? (score 0.758 -> 0.758)
- analysis: depth standard, format short
- answerer: drafted: This depends on your location and role. In Singapore, full-time employees receive 18 days of paid annual leave, rising to 21 days after 5 years of service [1]. In the United Kingdom, full-time employees receive 25 days of paid annual leave plus 8 publ
- validator: uncited: This depends on your location and role.
- answerer: retry: citations: The number of annual leave days depends on your location and role. In Singapore, full-time employees receive 18 days rising to 21 days after 5 years of service, with up to 7 unused days carried forward [1]. In the United Kingdom, full-time em
- validator: uncited: The number of annual leave days depends on your location and role.
- answerer: retry: citations: The number of annual leave days depends on your location and role. In Singapore, full-time employees receive 18 days of paid annual leave, rising to 21 days after 5 years of service [1]. In the United Kingdom, full-time employees receive 25 d
- validator: uncited: The number of annual leave days depends on your location and role.

## [unverified] how much can I spend on a client dinner per head  (asked by analyst, best score 0.184)
- refiner: search with: How much can I spend per head on a client dinner? (score 0.184 -> 0.184)
- analysis: depth standard, format short
- answerer: drafted: The daily meal allowance is INR 1,500, and client entertainment is reimbursed up to INR 4,000 per person for client dinners, but receipts are required for any item above INR 500 [1].
- validator: UNSUPPORTED The daily meal allowance is INR 1,500
- answerer: retry: grounding: The daily meal allowance is INR 1,500 [1]. For client entertainment, it is reimbursed up to INR 4,000 per person, but receipts are required for any item above INR 500 [1].
- validator: SUPPORTED
- validator: fit: no
- answerer: retry: fit: The daily meal allowance is INR 1,500, and client entertainment is reimbursed up to INR 4,000 per person for client dinners [1].
- validator: UNSUPPORTED The daily meal allowance is INR 1,500

## [unverified] how much maternity leave in the UK  (asked by analyst, best score 0.821)
- refiner: search with: How much maternity leave is available in the UK according to the official policy? (score 0.821 -> 0.821)
- analysis: depth quick, format short
- answerer: drafted: Maternity leave in the UK is 39 weeks, with the first 12 weeks on full pay. [1]
- validator: UNSUPPORTED Maternity leave in the UK is 39 weeks.; The first 12 weeks of maternity leave in the UK are on full pay.
- answerer: retry: grounding: Maternity leave in the UK is 39 weeks [1].
- validator: UNSUPPORTED Maternity leave in the UK is 39 weeks
- answerer: retry: grounding: Maternity leave in the UK is 39 weeks, with the first 12 weeks on full pay [1].
- validator: UNSUPPORTED Maternity leave in the UK is 39 weeks

## [unverified] how soon must I declare a conflict of interest  (asked by manager, best score 0.994)
- refiner: no change
- analysis: depth standard, format short
- answerer: drafted: According to the Conflicts of Interest Procedure, a conflict of interest must be declared to Compliance within 5 working days of becoming aware of it, using the conflicts register. Additionally, every employee is required to make an annual declaration
- validator: uncited: According to the Conflicts of Interest Procedure, a conflict of interest must be declared to Compliance within 5 working days of becoming aware of it,
- answerer: retry: citations: According to the Conflicts of Interest Procedure, a conflict of interest must be declared to Compliance within 5 working days of becoming aware of it, using the conflicts register [1]. However, the Code of Conduct states that an employee who 
- validator: uncited: Both documents provide different timelines, but the more stringent requirement should be followed.
- answerer: retry: citations: According to the Code of Conduct (NW-COC-004), an employee must declare a conflict of interest to their manager within 7 calendar days of becoming aware of it [2]. However, the Conflicts of Interest Procedure requires declaration to Complianc
- validator: UNSUPPORTED When there is a discrepancy, the more stringent requirement should be followed, which in this case is the 5 working days to Compliance.

## [unverified] under the old travel policy, what hotel limit applied in metro cities  (asked by analyst, best score 0.4)
- refiner: no change
- analysis: depth standard, format short
- answerer: drafted: Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night [2].
- validator: UNSUPPORTED Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night
- answerer: retry: grounding: Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night [2].
- validator: UNSUPPORTED Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night
- answerer: retry: grounding: Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night [2].
- validator: UNSUPPORTED Under the old travel policy, the hotel limit in metro cities was INR 9,000 per night

## [unverified] what is the carry forward limit for leave  (asked by analyst, best score 0.399)
- refiner: no change
- analysis: depth quick, format short
- answerer: drafted: The carry forward limit for leave varies by country:

- In Singapore, up to 7 unused days of annual leave may be carried forward to the next year [1]. - In the United Kingdom, up to 5 unused days of annual leave may be carried forward to the next year
- validator: uncited: The carry forward limit for leave varies by country:
- answerer: retry: citations: The carry forward limit for leave varies by country. In Singapore, up to 7 unused days of annual leave may be carried forward to the next year [1]. In the United Kingdom, up to 5 unused days of annual leave may be carried forward to the next 
- validator: uncited: The carry forward limit for leave varies by country.
- answerer: retry: citations: The carry forward limit for leave varies by country. In Singapore, up to 7 unused days of annual leave may be carried forward to the next year [1]. In the United Kingdom, up to 5 unused days of annual leave may be carried forward to the next 
- validator: uncited: The carry forward limit for leave varies by country.

## [unverified] what is the current deadline to submit travel claims  (asked by analyst, best score 0.937)
- refiner: no change
- analysis: depth standard, format short
- answerer: drafted: According to the Travel and Expense Policy 2025 (NW-TRV-025) [2], expense claims must be submitted within 30 days of the end of the trip. Claims submitted later are paid only with the approval of the finance controller.
- validator: uncited: Claims submitted later are paid only with the approval of the finance controller.
- answerer: retry: citations: According to the Travel and Expense Policy 2025 (NW-TRV-025) [2], expense claims must be submitted within 30 days of the end of the trip. Claims submitted later are paid only with the approval of the finance controller.
- validator: uncited: Claims submitted later are paid only with the approval of the finance controller.
- answerer: retry: citations: According to the Travel and Expense Policy 2025 (NW-TRV-025) [2], expense claims must be submitted within 30 days of the end of the trip. Claims submitted later are paid only with the approval of the finance controller.
- validator: uncited: Claims submitted later are paid only with the approval of the finance controller.

## [unverified] what is the daily meal allowance under the latest travel policy  (asked by analyst, best score 0.946)
- refiner: no change
- analysis: depth standard, format short
- answerer: drafted: The daily meal allowance under the latest travel policy is INR 1,800 [3].
- validator: UNSUPPORTED The daily meal allowance under the latest travel policy is INR 1,800
- answerer: retry: grounding: The daily meal allowance under the latest travel policy is INR 1,800 [1].
- validator: UNSUPPORTED The daily meal allowance under the latest travel policy is INR 1,800; The daily meal allowance under the latest travel policy is INR 1,500
- answerer: retry: grounding: The daily meal allowance under the latest travel policy is INR 1,500 [2].
- validator: UNSUPPORTED The daily meal allowance under the latest travel policy is INR 1,500
