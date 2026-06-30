help:
	@echo "kselftests - Kernel selftests"
	@echo "Available targets:"
	@echo "  prepare 	# download and install dependencies"
	@echo "  test 		# runs the kernel selftests"

prepare:
	@./install-deps.sh

test:
	+@./test.sh $(TARGET) $(KERNEL_SRC)

clean:
	rm -rf ~/kselftests-results

.PHONY: prepare test clean help
