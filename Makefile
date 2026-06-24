.PHONY: install plan render material narrate compose thumbnail run upload clean voicevox-up preview-run sample-run

install:
	pip install -r requirements.txt

plan:
	python scripts/chaosim.py plan --topic "$(TOPIC)"

render:
	python scripts/chaosim.py render $(CONCEPT)

material:
	python scripts/chaosim.py material $(CONCEPT)

narrate:
	python scripts/chaosim.py narrate $(CONCEPT)

compose:
	python scripts/chaosim.py compose $(CONCEPT)

thumbnail:
	python scripts/chaosim.py thumbnail $(CONCEPT)

run:
	python scripts/chaosim.py run $(CONCEPT)

upload:
	python scripts/chaosim.py upload $(VIDEO)

clean:
	rm -rf outputs/renders/* outputs/material/* outputs/audio/* outputs/work/* outputs/final/* outputs/uploads/*

# Start a local VOICEVOX engine (CPU) for narration.
voicevox-up:
	docker run --rm -p 50021:50021 voicevox/voicevox_engine:cpu-latest

# Full pipeline in stub mode — needs only ffmpeg (no Blender/HyperFrames/VOICEVOX).
preview-run:
	CHAOSIM_STUB=1 python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml

sample-run:
	python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
