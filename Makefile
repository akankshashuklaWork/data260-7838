PYTHON ?= .venv/bin/python

run-hw06:
	PYTHONPATH=code $(PYTHON) -m uvicorn hw6_memory.main:app --host 127.0.0.1 --port 8638

verify-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.verify

file-memory-demo-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.file_memory_demo

experiment-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.experiment $(ARGS)

run-hw07:
	PYTHONPATH=code $(PYTHON) -m uvicorn hw7.bike_ui:app --host 127.0.0.1 --port 8638

verify-hw07:
	PYTHONPATH=code $(PYTHON) -m hw7.verify_hw7

run-log-hw07:
	PYTHONPATH=code $(PYTHON) -m hw7.run_log

up-hw08:
	docker compose -f code/hw8/docker-compose.yml up -d --build

down-hw08:
	docker compose -f code/hw8/docker-compose.yml down -v

demo-hw08:
	cd code/hw8 && ../../$(PYTHON) homework_demo.py

pipeline-hw08:
	PYTHONPATH=code $(PYTHON) -m hw8.run_pipeline

failures-hw08:
	PYTHONPATH=code $(PYTHON) -m hw8.failure_tests

verify-hw08:
	PYTHONPATH=code $(PYTHON) -m hw8.verify_hw8

run-log-hw08:
	PYTHONPATH=code $(PYTHON) -m hw8.run_log

up-hw09:
	docker compose -f code/hw9/docker-compose.yml up -d
	docker compose -f code/hw8/docker-compose.yml up -d kafka kafka-init

down-hw09:
	docker compose -f code/hw9/docker-compose.yml down

run-hw09:
	PYTHONPATH=code $(PYTHON) -m uvicorn hw9.ingress:app --host 127.0.0.1 --port 8638

part1-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.part1_counter_demo

part2-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.part2_cache_demo

part3-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.part3_sweep
	PYTHONPATH=code $(PYTHON) -m hw9.part3_stale_demo

part4-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.part4.run_part4 all

verify-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.verify_hw9

run-log-hw09:
	PYTHONPATH=code $(PYTHON) -m hw9.run_log

# ---- HW10: Streamlit operations dashboard, evaluation, judge validation, tracing ----
# Kafka and Redis come from `make up-hw09`; the Ollama server must be running (qwen2:7b, qwen3:8b).
up-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.stack up

down-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.stack down

status-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.stack status

dashboard-hw10:
	PYTHONPATH=code $(PYTHON) -m streamlit run code/hw10/dashboard.py --server.port 8638 --server.address 127.0.0.1 --browser.gatherUsageStats false

eval-cases-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.build_eval_cases

label-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.label_drafts

traces-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.capture_traces

latency-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.loadtest
	PYTHONPATH=code $(PYTHON) -m hw10.analyze_latency

validate-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.validate_judge --sensitivity

finalize-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.finalize

verify-hw10:
	PYTHONPATH=code $(PYTHON) -m hw10.verify_hw10
