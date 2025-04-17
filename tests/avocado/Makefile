help:
	@echo "avocado-misc-tests"
	@echo "Available targets:"
	@echo "  prepare 	# download and install dependencies"
	@echo "  test 		# builds the tests"

prepare: 
	@./install-deps.sh

test:
	+@./test.sh $(FS) $(CONFIG)

clean:
	rm -rf xfstests log

.PHONY: download prepare test clean help
