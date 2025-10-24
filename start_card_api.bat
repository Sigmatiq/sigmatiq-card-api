@echo off
cd /d C:\sigmatiq\dev-2\repos\sigmatiq-card-api
set CARDS_DATABASE_URL=postgresql://postgres:flowpass123@localhost:5432/sigmatiq
set BACKFILL_DATABASE_URL=postgresql://postgres:flowpass123@localhost:5432/sigmatiq
uvicorn sigmatiq_card_api.app:app --host 0.0.0.0 --port 8007 --reload
