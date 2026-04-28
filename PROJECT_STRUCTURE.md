# Project Structure

```text
quality-driven-knowledge-engineering-platform/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── services/
│   ├── schemas/
│   ├── templates/
│   └── ui/
├── resources/
│   ├── policies/
│   ├── templates/
│   └── golden_datasets/
├── sample_packages/
├── benchmark_runs/
├── reports/
├── feedback/
├── exports/
├── tests/
├── scripts/
├── requirements.txt
├── .env.example
├── README.md
├── IMPLEMENTATION_LOG.md
└── PROJECT_STRUCTURE.md
```

## Main execution commands

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
streamlit run app/ui/streamlit_app.py
python scripts/run_local_benchmark.py
```
