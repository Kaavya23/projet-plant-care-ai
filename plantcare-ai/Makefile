.PHONY: install data train-c train-b api dash pipeline seed test up
install:   ; pip install -r requirements.txt
data:      ; python ml/generate_synthetic_data.py
train-c:   ; python ml/train_watering.py
train-b:   ; python ml/train_vision.py --epochs 3
seed:      ; python ml/seed_db.py
pipeline:  ; python pipelines/prefect_flows.py
api:       ; PYTHONPATH=src uvicorn plantcare.api.main:app --reload
dash:      ; streamlit run dashboard/app.py
test:      ; PYTHONPATH=src pytest -q
up:        ; docker compose up --build
