# Day 2: Agents and tools

## What I built

Today I built a read-only loan assistant. You ask it a question in plain English and it looks at the loan application's real database to answer: is this customer eligible, what is the interest rate, what will the EMI be. It runs on the local model (qwen3.5:9b through Ollama). It can only look. It cannot apply for, approve or change a loan.

I got there in small steps:

- **Labs 1 to 5** (`lab1_tool.py` to `lab5_errors.py`, plus `lab4b_harsh.py`): one tool, then an agent that uses it, then reading the message sequence, then the effect of the tool description, then what happens when a tool fails. One lesson from Lab 5: a tool that raises an error crashed the agent, so my tools return a friendly message instead.
- **Tools** (`loan_tools.py`): four tools that use the app's real data and the app's own code, so the answers match the app.
  - `get_customer`: name, age, income, existing EMI, approved loans and risk band. It leaves out email, phone and date of birth on purpose.
  - `check_eligibility`: checks every rule (age 21 to 60, amount at most 20 times monthly income, fewer than 2 approved loans) and lists all the ones that fail. The app itself stops at the first failure.
  - `get_interest_rate`: the rate for a tenure of 12, 24, 36, 48 or 60 months.
  - `emi_calculator`: monthly EMI, total payment and total interest.
- **Agent** (`loan_agent.py`): the four tools plus a system prompt. It must use tools for every number, ask when a customer id or amount is missing, say plainly when something is not found, and refuse anything that is not about loans.
- **Tests** (`test_loan_tools.py`): check the tools directly with no model involved. One test compares my eligibility tool with the app's own check for all 12 customers and 3 amounts each, so if the app's rules change, the test fails.

The database connection is opened in Postgres read-only mode. I proved that a write is refused.

**Added on Day 3:** the same agent now also has `search_policy` (answers from the loan policy document) and `percent_of` (works out fees like the processing fee), and its system prompt was rewritten as a short "for this kind of question, use this tool" list. The six results and `traces.txt` below were recorded before that change, so they describe the original four-tool agent. The two customer tools now also return a friendly message if the database is down, instead of crashing. See `day3_rag/README.md`.

## How to run

Make sure Ollama and the database are running, then:

```powershell
cd C:\loan_application\langchain-week
uv run python day2_agents\test_loan_tools.py
uv run python day2_agents\loan_agent.py
```

The tests take a few seconds. The agent runs six questions and saves the full output to `traces.txt`. It takes about 10 minutes because the model runs on my CPU and each question needs about two model calls.

(`.env` needs `LOAN_DB_URL`, the same database URL the app uses.)

## Results

The six questions, in order (see `traces.txt`):

| # | Question | What the agent did |
|---|---|---|
| 1 | EMI for 3,00,000 at 10.5% for 24 months | Called `emi_calculator`, answered 13,912.81 |
| 2 | Customer 29 for 5,00,000 over 36 months | Called `get_customer` and `check_eligibility`, said eligible |
| 3 | Customer 4 for 4,00,000 over 24 months | Called `check_eligibility`, said not eligible because of age |
| 4 | Customer 999 | Called `check_eligibility`, said the customer was not found |
| 5 | Capital of France | No tool call, politely refused |
| 6 | "Can I get a loan?" | No tool call, asked for customer id and amount |

Question 3 fails only on age. The assignment guide expected age and the 2-loans rule, but customer 4's loans were wrongly approved earlier and I fixed that (see below), so the 2-loans rule no longer applies.

## Tool descriptions

1. The model sees only a tool's name, parameter names and description, never the code inside.
2. Lab 4b: with the description "does maths", the model still called the tool with the right arguments (p=500000, r=11, n=36) and got 16,369.36, the same as with the clear description.
3. That worked because there was only one tool and the question was unambiguous. It shows a small model can infer a lot from names and types, but it is luck, not a guarantee.
4. With several tools, the description is the only way the model can choose between them, so each one should state what it does, the unit of each argument, and what it returns on bad input.
5. In the loan agent, with four tools, every description is specific, and all six questions chose the right tool or correctly chose none.

## Known limits

- **No access control.** The app lets officers see every customer and customers only their own. My tools read the database directly and don't know who is asking, so anyone who can chat with the agent can look up any customer. This is fine on my machine with dev data, but it must be fixed before real use: log the user in and lock each session to their own customer id, or call the app's API so its rules apply.
- **Credit score added after Day 2.** The app now calculates a credit score (300 to 850, at least 600 to be eligible) from income, existing EMI and age. `check_eligibility` and `get_customer` report it. The six results above were recorded before it existed, so they show only the original three rules.
- **Tracing is off.** Real customer data flows through the tools, so I kept LangSmith tracing switched off. I print the message sequence instead.
- **Slow.** About 20 seconds per model call on CPU.

## What surprised me

While testing, I asked why customer 6, aged 5, had an approved loan. The cause was a bug in the app: `approve_loan` never checked eligibility, so an officer could approve a loan for anyone. I fixed it so it uses the same rules as applying, added three tests, and rejected the three wrongly approved loans in the dev database.

I was also surprised that the vague description worked in Lab 4b. I expected it to fail.
