# LangChain & LangGraph: 5-Day Hands-On Week

Loan Assistant built across five days. Model: local Ollama `qwen3.5:9b`.

| Day | Folder | Builds |
|-----|--------|--------|
| Mon | day1_langchain | Loan-enquiry reader (structured output) |
| Tue | day2_agents | Agent with tools |
| Wed | day3_rag | Policy Q&A with citations |
| Thu | day4_langgraph | Pre-screening workflow |
| Fri | day5_capstone | Approval, memory, tracing, capstone |

Setup: packages live in the root project's `dev` dependency group, so run `uv sync` in `C:\loan_application`, copy `.env.example` to `.env`, then from this folder run `uv run python hello.py`.
