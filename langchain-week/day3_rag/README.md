# DAY 3: GIVING THE MODEL A DOCUMENT (RAG)

## What I built

Today I taught the assistant to answer from a document instead of from memory. I wrote a sample loan policy, and now when someone asks "can I prepay my loan?", the code first finds the right part of the policy, hands only that part to the model, and tells it to answer from it and cite the section number. If the policy doesn't say, the model has to admit it.

I also joined it to Monday's assistant. The chat in day2_agents/loan_agent.py now answers customer questions from the live database and policy questions from the document, in the same conversation.

About the policy file: the guide gave a sample policy, but its rules don't match our app (it wants a credit score of 700, ours needs 600). So I kept the parts the app has, with the app's real rules, and left the parts it doesn't have (fees, prepayment, documents, disbursal) as the guide wrote them. That is data/loan_policy.txt. The guide's original is kept next to it as data/loan_policy_guide.txt, so I can compare the two.

The labs, one file each:

- Lab 1 (lab1_load_split.py): loads the policy and cuts it into 9 chunks. Each chunk is tagged with its document name.
- Lab 2 (lab2_embed_search.py): turns the chunks into numbers and searches by meaning. "How soon is the money paid out?" finds the disbursal rule even though the question never says "disbursal".
- Lab 3 (lab3_ask.py): fetches three chunks and lets the model answer from them with a section number.
- Lab 4 (lab4_break_retriever.py): breaks the search on purpose with chunks of 80 and 2000 characters.
- Lab 5 (lab5_tool.py): wraps the search as a tool and gives it to an agent next to the EMI calculator.

The assignment pieces:

- build_index() (in policy_rag.py): loads, splits, embeds and stores the policy in one call. It takes a chunk size, so I can run the same thing at different sizes.
- ask_policy() (ask_policy.py): returns the answer and the section numbers it used. For anything the policy doesn't cover, it says "I could not find this in the policy."
- run_questions.py: runs the guide's ten questions and writes answers.md.
- experiment.py: runs the ten questions at two chunk sizes. The write-up is in experiment_note.md.
- search_policy and percent_of (policy_tools.py): the two tools I added to Monday's agent. percent_of works out percentages like the processing fee, because the model can't be trusted with sums (see below).
- demo_combined.py: five questions for the joined-up agent, saved with the tool-call order in demo_combined.txt.

There are also small tests that don't need the chat model: test_build_index.py, test_policy_tools.py and test_ask_policy.py.

## How to run

Make sure Ollama is running (the embedding model nomic-embed-text has to be installed once with ollama pull nomic-embed-text). Then, from the day3_rag folder:

```powershell
cd C:\loan_application\langchain-week\day3_rag
uv run python -W ignore lab1_load_split.py      # instant
uv run python -W ignore lab2_embed_search.py    # a few seconds
uv run python -W ignore lab3_ask.py             # about 1 minute
uv run python -W ignore run_questions.py        # the ten questions, about 4 minutes
uv run python -W ignore experiment.py           # both chunk sizes, about 8 minutes
```

For the combined assistant, Docker and the database must also be running, because it reads real customers:

```powershell
cd C:\loan_application\langchain-week
uv run python day2_agents\loan_agent.py          # the chat
uv run python -W ignore day3_rag\demo_combined.py   # the five demo questions
```

(-W ignore only hides a warning that one of the libraries is being retired. It's not needed.)

## Results

All ten questions pass at chunk size 300, and I read every answer myself, not just the automatic check. Questions 1 to 8 are correct with the right sections. Question 9 (gold loans) says it could not find it, and question 10 (the rate for a 750 score) says the rate depends on the tenure and doesn't invent one. One answer is incomplete: for the processing fee it says "1.5 percent plus taxes" and doesn't give the rupee amount, because ask_policy does no sums on purpose.

At chunk size 80, three more answers fail. The full story is in experiment_note.md, but in short:

- The rate question lost its answer because the three search results were all overlapping pieces of the credit score rule, so the interest rule never made it in.
- Two answers lost their section number or the end of a sentence because a chunk was cut in the wrong place.
- The processing fee question was a model problem, not a search problem: the right rule was found, but the model said "I could not find this" while quoting it.

The joined-up assistant handled all five demo questions (see demo_combined.txt). It used the live data for customers, the policy for documents and disbursal, and both together for "is customer 29 eligible, and what documents do they need?"

## Things that are not perfect

- The model can still skip a tool. In the demo the processing fee came out as ₹9,000, which is right, but the model worked it out itself instead of calling percent_of. Earlier it once turned ₹9,000 into ₹90,000. I can't count on the right answer unless a tool does the sum.
- One answer came from the prompt, not a tool. "What credit score do I need?" was answered from the number written in the prompt. It's correct, but if the policy changed, the prompt would still say 600.
- The policy is a copy of the app's rules. If someone changes a rule in the app, the policy file has to be updated by hand.
- The automatic check is only keywords. It looks for the expected section and words. A pass doesn't prove the wording is perfect, so I read the answers too.
- The index is rebuilt every time. It lives in memory and takes a few seconds to build. That's fine for one small document.
- Tracing is off. The joined-up assistant reads real customers, so I didn't send anything to LangSmith.
ther. Every time I added a rule to fix one answer, another answer got worse. A rule to include conditions fixed the prepayment answer. A rule to show the amount made the model write ₹90,000 instead of ₹9,000. Adding "keep the answer short" earlier had probably been the reason it dropped the 2% charge in the first place. In the end the joined-up assistant only worked once I rewrote its long list of rules as a short "for this kind of question, use this tool" list, and gave the sums to a tool.

The other surprise was the overlap setting. At normal chunk sizes it does nothing at all here, because every policy line fits whole. It only shows up when a line gets cut in half, which is the one case where it matters.
