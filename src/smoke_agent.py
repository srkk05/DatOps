from agent import run_question

QUESTIONS = [
    "Top 5 mandis by arrivals",
    "Which mandis are below MSP?",
    "What is the risk for MANDI047?",
    "Show wheat arrivals for the last 30 days",
    "What is the wheat price?",
    "Which mandis have both high price pressure and slow logistics?",
    "Plot the daily arrival trend of Wheat in Amritsar mandi vs MSP for the last 30 days",
]

for q in QUESTIONS:
    print("\n" + "=" * 90)
    print(q)
    try:
        r = run_question(q)
        print("intent:", r["intent"])
        print("chart:", r["chart_type"])
        print("rows:", r["row_count"])
        print("summary:", r["summary"])
        print(r["data"].head(5).to_string(index=False))
    except Exception as exc:
        print("ERROR:", type(exc).__name__, exc)
