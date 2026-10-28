# Day 1: LangChain building blocks

## What I built

Today I built a small tool that reads a messy customer email and pulls out the loan details in a neat, structured form: name, amount, tenure in months, and purpose. It runs on a local model (qwen3.5:9b through Ollama), so nothing leaves my machine except the LangSmith traces.

I got there in small steps, one file per lab:

- **Lab 1** (`lab1_messages.py`): asked the same question twice with a different system message, and got a formal answer and a casual one.
- **Lab 2** (`lab2_template.py`): wrote one prompt template with a blank for the email and reused it on three emails.
- **Lab 3** (`lab3_structured.py`): made the model fill a `LoanEnquiry` class instead of writing a paragraph.
- **Lab 4** (`lab4_chain.py`): chained the prompt and the model together, ran three emails at once with `.batch`, and streamed a reply word by word.
- **Assignment** (`enquiry_reader.py`): the full reader for all five sample emails. It prints a table, saves the output to `results.txt`, and checks itself with asserts.
- **Retry proof** (`test_retry.py`): a small test that makes the model fail on purpose, so I can show the retry works.

How the reader behaves:

- It never guesses. If an email doesn't say something, that field stays empty and is listed in `missing_fields`.
- It converts units for me: 25L becomes 2,500,000 and 5 years becomes 60 months.
- If a call fails, it tries once more. If that fails too, it returns a clear "could not read" result instead of crashing. An empty email gets that result straight away.

## How to run

Make sure Ollama is running, then from the `langchain-week` folder:

```powershell
cd C:\loan_application\langchain-week
uv run python day1_langchain\enquiry_reader.py
```

That runs all five emails and writes `results.txt`. It takes about two minutes because the model runs on my CPU. To check the retry behaviour:

```powershell
uv run python day1_langchain\test_retry.py
```

(First time only: run `uv sync` in `C:\loan_application` and copy `.env.example` to `.env`.)

## Results

All the asserts pass. Priya's email, which has no amount or tenure, comes back with both left empty and listed as missing, which is what it should do.

## Tracing

Tracing is switched on in LangSmith. In one batch run (the Priya email), the model step used 173 input tokens and 44 output tokens, 217 in total, and the first token took about 20 seconds to arrive.

Screenshots: `trace_tokens.png` and `trace_system_message.png`.

## What surprised me

How much the speed depended on one setting. My first test took 4 to 7 minutes per email. After switching off the model's thinking mode (`reasoning=False`), it dropped to about 20 seconds. The trace also showed that most of those 20 seconds are the model reading the prompt, not writing the answer.

I was also surprised that the structured output gave me the right type but not always the right values. At first it read "25L" as 25 and missed the name in "Suresh here". I fixed both by writing the rules into the prompt.
