# Contributing to TRAVOO

1. Create a branch from `main`: `git checkout -b feature/short-name`.
2. Backend: keep every route under `/api`. Run `pytest -q` in `backend/` before pushing.
3. Frontend: use React Native components only, take colours from `src/theme.ts`, and add a `testID` to interactive elements. Run `yarn lint` and `npx tsc --noEmit`.
4. New UI text: add the key to `frontend/src/i18n/locales/en.json`, then run `python backend/scripts/translate.py` (needs an LLM key) or add the translations by hand.
5. Never commit secrets. `.env` files are git-ignored, so update the `.env.example` files when you add a variable.
6. Payments stay direct (cash/UPI). Do not add a payment gateway without a product decision.
7. Phone numbers must stay hidden until a booking is confirmed.
8. Open a pull request with a short description and screenshots for UI changes.
