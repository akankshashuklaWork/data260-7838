PYTHON ?= .venv/bin/python

run-hw06:
	PYTHONPATH=code $(PYTHON) -m uvicorn hw6_memory.main:app --host 127.0.0.1 --port 8638

verify-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.verify

file-memory-demo-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.file_memory_demo

experiment-hw06:
	PYTHONPATH=code $(PYTHON) -m hw6_memory.experiment $(ARGS)
