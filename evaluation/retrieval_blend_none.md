# Retrieval check

Embedding: local / sentence-transformers/all-MiniLM-L6-v2 / 384

86-question set, 37 answerable questions, search (before rerank, top 10): right document first 86%, in top 3 97%, in top 5 100%, MRR 0.924
86-question set, 37 answerable questions, after rerank (top 5): right document first 89%, in top 3 92%, in top 5 92%, MRR 0.905

Not ranked first after rerank:
- rank not found: Which function loses the fewest people?  (expected Employee Attrition and Turnover Report)
- rank 2: How ofen are performence reveiws held?  (expected Performance Review and Promotion Process)
- rank not found: What cheks are done on a new cleint befor we let them transact?  (expected KYC and AML Procedures)
- rank not found: Wich team has the worst staf retenton?  (expected Employee Attrition and Turnover Report)

27-question set, 12 answerable questions, search (before rerank, top 10): right document first 92%, in top 3 100%, in top 5 100%, MRR 0.958
27-question set, 12 answerable questions, after rerank (top 5): right document first 100%, in top 3 100%, in top 5 100%, MRR 1.000

