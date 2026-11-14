# Retrieval check

Embedding: local / sentence-transformers/all-MiniLM-L6-v2 / 384

86-question set, 37 answerable questions, search (before rerank, top 10): right document first 86%, in top 3 97%, in top 5 100%, MRR 0.924
86-question set, 37 answerable questions, after rerank (top 5): right document first 89%, in top 3 95%, in top 5 100%, MRR 0.927

Not ranked first after rerank:
- rank 2: When do I need director sign-off on a contract?  (expected Vendor Selection and Procurement Policy)
- rank 4: Which function loses the fewest people?  (expected Employee Attrition and Turnover Report)
- rank 5: What cheks are done on a new cleint befor we let them transact?  (expected KYC and AML Procedures)
- rank 3: Wich team has the worst staf retenton?  (expected Employee Attrition and Turnover Report)

27-question set, 12 answerable questions, search (before rerank, top 10): right document first 92%, in top 3 100%, in top 5 100%, MRR 0.958
27-question set, 12 answerable questions, after rerank (top 5): right document first 100%, in top 3 100%, in top 5 100%, MRR 1.000

