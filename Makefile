# Pragati Makefile (run every target from the repository root)

.PHONY: test-contracts test-contracts-db

test-contracts:
	python -m pytest contracts/tests -v -rs

test-contracts-db:
	python -m pytest contracts/tests -m db -v -rs

# === datagen ===
.PHONY: test-datagen
test-datagen:
	python -m pytest datagen/tests -v -rs

# === public_validation ===
.PHONY: test-public test-public-data
test-public:
	python -m pytest ml/public_validation/tests -m "not data" -v -rs

test-public-data:
	python -m pytest ml/public_validation/tests -v -rs

# === genai_reports ===
.PHONY: test-genai
test-genai:
	python -X utf8 -m pytest backend/app/genai/tests -v -rs




# === Backend (Windows-friendly) ===
.PHONY: train seed demo-native test-api
train:
	cd backend && python -X utf8 -m app.ml.train

seed:
	cd backend && python -X utf8 -m app.db.seed

# start the local database, seed if empty, serve the API on http://127.0.0.1:8000
demo-native:
	cd backend && python -X utf8 -m app.cli demo

test-api:
	cd backend && python -X utf8 -m pytest tests -q
