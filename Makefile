PYTHON ?= python3
LANG_CODE ?= en
SHOT ?=

.PHONY: help setup validate film film-am radio-cut radio-cut-am \
	stage-script stage-narration stage-narration-offline stage-music \
	stage-keyframes stage-ref-sheet stage-shots stage-assemble clean-cache

help:
	@echo "Red Through the Years — Heritage Short Pipeline"
	@echo ""
	@echo "Main targets:"
	@echo "  make film              Validate storyboard and run full available pipeline"
	@echo "  make radio-cut         Build Phase 1 radio cut -> outputs/radio-cut.mp4"
	@echo "  make validate          Validate storyboard.json against schema + guardrails"
	@echo "  make setup             Optional: install requirements.txt (pipeline also works stdlib-only)"
	@echo ""
	@echo "Per-stage targets:"
	@echo "  make stage-script              Inspect & validate storyboard beats"
	@echo "  make stage-narration           Generate narration via Gemini TTS (LANG_CODE=en|am; requires GEMINI_API_KEY)"
	@echo "  make stage-narration-offline   Generate offline placeholder cues for dry-run testing"
	@echo "  make film-am                   Build Amharic-audio finals (EN burned-in subtitles kept)"
	@echo "  make stage-music               Prepare ACE-Step score or Phase 1 warm ambient bed"
	@echo "  make stage-ref-sheet           Phase 2: generate FLUX character reference sheet"
	@echo "  make stage-keyframes           Phase 2: generate FLUX keyframes (pass SHOT=shot_01 for one shot)"
	@echo "  make stage-shots               Phase 2: conform Wan 2.2 clips or render Ken Burns shots"
	@echo "  make stage-assemble            Assemble outputs/radio-cut.mp4 (or full film when shots exist)"
	@echo "  make clean-cache               Remove outputs/cache/ intermediates"

setup:
	$(PYTHON) -m pip install -r requirements.txt

validate:
	$(PYTHON) -m pipeline.validate

film:
	$(PYTHON) -m pipeline.run film --lang $(LANG_CODE)

film-am:
	$(PYTHON) -m pipeline.narration --lang am
	$(PYTHON) -m pipeline.music --lang am
	$(PYTHON) -m pipeline.assemble --mode film --lang am

radio-cut:
	$(PYTHON) -m pipeline.run radio-cut --lang $(LANG_CODE)

radio-cut-am:
	$(PYTHON) -m pipeline.narration --lang am
	$(PYTHON) -m pipeline.music --lang am
	$(PYTHON) -m pipeline.assemble --mode radio-cut --lang am

stage-script:
	$(PYTHON) -m pipeline.script

stage-narration:
	$(PYTHON) -m pipeline.narration --lang $(LANG_CODE) $(if $(SHOT),--shot $(SHOT),)

stage-narration-offline:
	$(PYTHON) -m pipeline.narration --lang $(LANG_CODE) --allow-placeholder $(if $(SHOT),--shot $(SHOT),)

stage-music:
	$(PYTHON) -m pipeline.music --lang $(LANG_CODE)

stage-ref-sheet:
	$(PYTHON) -m pipeline.keyframes --ref-sheet

stage-keyframes:
	$(PYTHON) -m pipeline.keyframes $(if $(SHOT),--shot $(SHOT),)

stage-shots:
	$(PYTHON) -m pipeline.shots --aspect 16:9 $(if $(SHOT),--shot $(SHOT),)
	$(PYTHON) -m pipeline.shots --aspect 9:16 $(if $(SHOT),--shot $(SHOT),)

stage-assemble:
	$(PYTHON) -m pipeline.assemble --mode radio-cut --lang $(LANG_CODE)

clean-cache:
	rm -rf outputs/cache
