# Policy Q&A answers

Policy: data/loan_policy.txt, chunk size 300, overlap 50.

Automatic keyword check: 10 of 10 PASS. CHECK means read the answer yourself; it does not always mean wrong.

## 1. What is the minimum age?

- **Answer:** The minimum age for an applicant is 21 years [1.1].
- **Sections used:** 1.1
- **A good answer contains:** 21 (section 1.1)
- **Check:** PASS

## 2. What happens if my credit score is 680?

- **Answer:** If your credit score is 680, you meet the requirement of having a credit score of 600 or above [1.3].
- **Sections used:** 1.3
- **A good answer contains:** 680 is above the minimum of 600, so the score rule is met (1.3)
- **Check:** PASS

## 3. What is the processing fee on a 6,00,000 loan?

- **Answer:** The processing fee is 1.5 percent of the loan amount plus applicable taxes [3.2].
- **Sections used:** 3.2
- **A good answer contains:** 1.5 percent plus taxes, so 9,000 plus taxes (3.2); ask_policy does no sums, so the rate is enough
- **Check:** PASS

## 4. Can I prepay after 8 months?

- **Answer:** Yes, you can prepay after 8 months because prepayment is allowed after 6 months [3.3]. However, since 8 months is within 12 months, a charge of 2 percent applies to the outstanding principal [3.3].
- **Sections used:** 3.3
- **A good answer contains:** Yes. A 2 percent charge applies within 12 months (3.3)
- **Check:** PASS

## 5. What income proof does a self-employed applicant need?

- **Answer:** A self-employed applicant needs to provide the last 2 years of ITR as income proof [4.3].
- **Sections used:** 4.3
- **A good answer contains:** Last 2 years of ITR (4.3)
- **Check:** PASS

## 6. Who approves a 12,00,000 loan?

- **Answer:** A senior manager approves loans above Rs 10,00,000 [2.3].
- **Sections used:** 2.3
- **A good answer contains:** A senior manager (2.3)
- **Check:** PASS

## 7. How long until disbursal?

- **Answer:** Approved loans are disbursed within 3 working days after documents are verified [5.1].
- **Sections used:** 5.1
- **A good answer contains:** 3 working days after verification (5.1)
- **Check:** PASS

## 8. Can the money go to my friend's account?

- **Answer:** No, the money cannot go to your friend's account. Disbursal is made only to the applicant's own bank account [5.2].
- **Sections used:** 5.2
- **A good answer contains:** No, only the applicant's own account (5.2)
- **Check:** PASS

## 9. What is the policy on gold loans?

- **Answer:** I could not find this in the policy.
- **Sections used:** none
- **A good answer contains:** Not in the policy. Must say it could not find it.
- **Check:** PASS

## 10. What interest rate will I get with a 750 score?

- **Answer:** The policy does not link the credit score to the interest rate; the interest rate depends on the tenure [3.1]. A credit score of 600 or above is required, but the specific score (e.g., 750) does not determine the rate [1.3], [3.1].
- **Sections used:** 3.1, 1.3
- **A good answer contains:** The rate depends on the tenure (10 to 13 percent), not the score (3.1). Must not invent a rate.
- **Check:** PASS
