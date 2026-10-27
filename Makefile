.PHONY: test backend-test frontend-test

test: backend-test frontend-test

backend-test:
	cd backend && .venv/bin/pytest

frontend-test:
	cd frontend && npm test && npm run typecheck
