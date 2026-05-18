.PHONY: install plan render run upload clean

install:
	pip install -r requirements.txt

plan:
	python scripts/chaosim.py plan --topic "$(TOPIC)"

render:
	python scripts/chaosim.py render $(CONCEPT)

run:
	python scripts/chaosim.py run $(CONCEPT)

upload:
	python scripts/chaosim.py upload $(VIDEO)

clean:
	rm -rf outputs/renders/* outputs/uploads/*

sample-run:
	python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
