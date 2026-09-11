.PHONY: test build

test:
	./scripts/verify-foundation.sh test
	./scripts/verify-text-baseline.sh test

build:
	./scripts/verify-foundation.sh build
	./scripts/verify-text-baseline.sh build
