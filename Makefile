MIGRATIONS_DIR := db/migrations

# Usage: make dev        — rebuild images and start the stack (override file auto-merged)
#        make dev v=1    — wipe volumes first, then rebuild and start
.PHONY: dev
dev:
	@if [ -n "$(v)" ]; then docker compose down -v; fi
	docker compose up --build -d

# Usage: make migration name=add_users_table
.PHONY: migration
migration:
	@test -n "$(name)" || (echo "Usage: make migration name=<description>"; exit 1)
	@file="$(MIGRATIONS_DIR)/$$(date +%Y%m%d%H%M%S)_$(name).sql"; \
	printf -- '-- migrate:up\n\n\n-- migrate:down\n' > "$$file"; \
	echo "Created $$file"
