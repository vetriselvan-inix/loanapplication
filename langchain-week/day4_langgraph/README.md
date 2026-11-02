# DAY 4: LANGGRAPH, THE FLOWCHART YOU CONTROL

## What I built

Today I built a loan pre-screening flowchart. You give it an email and a customer id, and it follows a fixed path to a decision: approve, refer to an officer, reject, or need more information. Every run also gives a plain reason and a log of the boxes it went through, so any decision can be explained step by step.

Which boxes use the model, and why only that one: only the first box, intake, uses the model. It reads a messy email ("5 lakh for 3 years to renovate my house") into an amount and a tenure, and that is something plain code cannot do. Every other box is ordinary code: validate, score, and the four decision boxes. The rules (age, income, burden, credit score) are known in advance and must give the same answer every time, so the model is kept out of them. The model only reads, and it never decides. That is also why this is a graph and not an agent. An agent chooses its own path, which suits open questions. A bank decision needs a fixed, ordered path that can be audited, and the graph gives that.

The labs, one file each:

- Lab 1 (lab1_smallest.py): the smallest graph. Two boxes turn "hello" into "HELLO!".
- Lab 2 (lab2_branch.py): a branch. Short and long texts take different paths, and stream_mode="updates" shows which.
- Lab 3 (lab3_reducers.py): reducers. A plain log is overwritten by every box and ends up as just ['third']. With operator.add it keeps ['first', 'second', 'third'].
- Lab 4 (lab4_draw.py): draws a graph as a Mermaid diagram (lab4_diagram.md).
- Lab 5 (lab5_model_node.py): a box that calls the Day 1 email reader and puts the amount and tenure in the state.

The assignment pieces:

- prescreen_graph.py: the graph. The boxes are intake, validate, score, and approve, refer, reject and need_info. A diamond after score picks one of the four.
- graph.md: the diagram, exported from the real graph.
- test_prescreen_graph.py: 16 checks that need no model, database or password. The email reader and the loan application are both simulated.
- prescreen_tool.py: the graph as a tool, prescreen_loan, so the chat in day2_agents/loan_agent.py can run it. The agent decides when to call it and the graph decides how. It uses the same login limits as the other customer tools, and it skips the email-reading box because the agent has already read the amount and tenure. Its checks are in test_prescreen_tool.py (10 checks, no model or database).
- setup_test_customers.py: creates the six test customers in the real app, and a starting loan for two of them. By default it only shows what it would create, and a second run only adds the missing ones.
- run_cases.py: runs the eight cases with the real model and the real app, and writes test_output.txt.

The routing order is the guide's: missing information first, then failed rules, then anything that needs a person's eye, otherwise approve.

I used our app's rules and real customers instead of the guide's sample ones, so a few numbers differ from the guide:

| | The guide | This graph |
|---|---|---|
| Customers | the sample C101 to C105 | real customers read through the app, with the officer's login |
| Interest rate | fixed 11% | the app's rate for the tenure (10% to 13%) |
| Credit score | below 650 reject, 650 to 699 refer | below 550 reject, 550 to 599 refer to an officer, 600 and above approve (600 is the app's minimum) |
| Burden | existing plus new EMI at most 50% of income | the same, taken from the guide's policy 1.4 (our policy has no such rule) |

A customer who logs in can screen only their own account, and an officer can screen anyone. The graph keeps only the customer's id, name and income. It never keeps the email, phone number or date of birth.

## How to run

Docker and the database must be running, because it reads real customers, and so must Ollama. The graph needs an officer login. The password is typed hidden and is never written to a file:

```powershell
cd C:\loan_application\langchain-week
$env:LOAN_USER = "vetri"
$p = Read-Host "Password" -AsSecureString
$env:LOAN_PASSWORD = [System.Net.NetworkCredential]::new("", $p).Password

uv run python -W ignore day4_langgraph\setup_test_customers.py            # shows the plan only
uv run python -W ignore day4_langgraph\setup_test_customers.py --create   # once: creates the test customers
uv run python -W ignore day4_langgraph\run_cases.py                       # the eight cases, about 5 minutes
uv run python -W ignore day4_langgraph\prescreen_graph.py                 # redraws graph.md
uv run python -W ignore day4_langgraph\test_prescreen_graph.py            # the offline checks, instant
```

The labs run on their own with uv run python -W ignore day4_langgraph\lab1_smallest.py and so on. Lab 5 needs Ollama.

## Results

All eight decisions match, and each log shows the path the case took (see test_output.txt). Cases 1 to 7 follow the guide's six, plus one for the score rule; case 8 shows what the moved refer band means for a score of 650.

| Case | Customer | Email says | Decision | Why |
|---|---|---|---|---|
| 1 | 32 | 5 lakh, 3 years | approve | score 820, EMI is 19.5% of income |
| 2 | 33 | 12,00,000, 60 months | refer | amount above 10,00,000 |
| 3 | 34 | 7 lakh, 24 months | reject | EMI would be 81.6% of income |
| 4 | 37 | 1 lakh, 36 months | refer | score 575 is between 550 and 599 |
| 5 | 32 | "a loan for a car" | need_info | amount and tenure missing |
| 6 | 999999 | 3 lakh, 2 years | need_info | customer not found |
| 7 | 36 | 10,000, 5 years | reject | score 546 is below 550 |
| 8 | 35 | 2.5 lakh, 36 months | approve | score 650 passes, EMI is 41.5% of income |

In cases 5 and 6 the log says "score (skipped)", because there is nothing to score yet. The app is not asked for the EMI summary or the eligibility rules in those cases.

## Things that are not perfect

- The refer band is not the app's. The app only knows the minimum of 600 and rejects anything below it. The graph instead refers scores of 550 to 599 to an officer, and ignores the app's own score rule for them. If that customer then applies for the loan in the app, the app will still refuse it, and nothing in the app lets an officer override that. The band only means "an officer should look at this".
- The 550 and 600 limits are my choice. The guide's referral band was 650 to 699.
- The burden rule lives only in the graph. The app itself has no 50% check. It only counts existing EMIs in the credit score.
- The customer id is not read from the email. It is passed in separately, as the guide does. A name in the email is ignored.
- If the app is down or the login has expired, the graph stops with an error instead of giving a decision. A made-up need_info would be misleading.
- A customer asking about someone else's id gets need_info with "You are not allowed to see that". There is no fifth outcome for it.
- The test customers stay in the database. Nothing deletes them, and the setup script refuses to run twice.
- This only pre-screens. It does not apply for or approve anything.

## One thing that surprised me

I could not make a new customer score below 600 just by giving them a low income or a young age. With no loans the EMI part of the score is full, so even a tiny income only brought the score down to about 610. To test the refer and reject-by-score cases I had to give two customers a loan that is already running, which drops the EMI points. One scores 575 after a 1.8 lakh loan (refer), the other 546 after a 2.5 lakh loan (reject), and even a 10,000 request is then judged on the score alone.

The other surprise was an error message. When I tried to rename a test customer, the app said "Customer with this email already exists", although the email was new. The real problem was a digit in the name, which the database refuses. The app turned every database refusal on create and update into that email message. I fixed it: a bad name is now a clear 400, a duplicate phone number gets its own message, and the fallback no longer blames the email.
