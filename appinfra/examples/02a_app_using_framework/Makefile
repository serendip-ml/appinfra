# Example: Application using the infra framework
#
# This Makefile demonstrates how to extend and customize the infra framework
# for your own application.

# Override framework variables BEFORE including framework files
PYTHON = ~/.venv/bin/python
COVERAGE_PKG = myapp  # Measure coverage for 'myapp' package (not infra)

# Path to framework root (adjust for your project structure)
framework_root := ../../

# Include framework Makefiles (selectively choose what you need)
include $(framework_root)/scripts/make/Makefile.help
include $(framework_root)/scripts/make/Makefile.utils
include $(framework_root)/scripts/make/Makefile.clean
include $(framework_root)/scripts/make/Makefile.dev
include $(framework_root)/scripts/make/Makefile.pytest
include $(framework_root)/scripts/make/Makefile.docs
# include $(framework_root)/scripts/make/Makefile.pg  # Uncomment if you use PostgreSQL

##@ App-Specific

# Extend framework's clean target with app-specific cleanup
clean::
	@echo "* app cleanup..."
	@echo "  - Removing app cache..."
	@rm -rf .app-cache/
	@echo "  - Removing temporary files..."
	@rm -rf .tmp/
	@echo "  - Stopping app services..."
	@# docker-compose -f docker-compose.app.yaml down -v

# Extend framework's lint target with app-specific checks
lint::
	@echo "* app-specific linting..."
	@echo "  - Checking API schema..."
	@# ./scripts/check-api-schema.sh
	@echo "  - Validating configuration..."
	@# ./scripts/validate-config.sh

# Extend framework's test targets with app-specific tests
test.integration::
	@echo "* running app API tests..."
	@# ./scripts/test-api.sh

test.e2e::
	@echo "* running app end-to-end tests..."
	@# ./scripts/test-e2e.sh

# Add completely new targets specific to your app
.PHONY: deploy
deploy: test  ## Deploy application to production
	@echo "* deploying application..."
	@echo "  NOTE: This is a placeholder - implement your deployment logic"
	@# ./scripts/deploy.sh

.PHONY: db.migrate
db.migrate:  ## Run database migrations
	@echo "* running database migrations..."
	@# $(PYTHON) -m alembic upgrade head

.PHONY: dev.up
dev.up:  ## Start development environment
	@echo "* starting development environment..."
	@# docker-compose -f docker-compose.dev.yaml up -d
	@# make pg.server.up

.PHONY: dev.down
dev.down:  ## Stop development environment
	@echo "* stopping development environment..."
	@# docker-compose -f docker-compose.dev.yaml down
	@# make pg.server.down

.PHONY: app.build
app.build:  ## Build application artifacts
	@echo "* building application..."
	@# $(PYTHON) -m build
	@# docker build -t myapp:latest .

.PHONY: app.run
app.run:  ## Run the application locally
	@echo "* running application..."
	@# $(PYTHON) -m myapp.main
