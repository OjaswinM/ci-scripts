help:
	@echo "clang"
	@echo "Available targets:"
	@echo "  download       # download and unpack default clang version"
	@echo "  download-all   # download and unpack all clang versions"
	@echo ""
	@echo "Download additional versions with:"
	@echo "  $ make llvm-<version>"

# Args:
#  1 = LLVM version
#  2 = RHEL version of the package
define TEMPLATE =
llvm-$(1):
	rm -f llvm-$(1).tar.xz
	wget --no-verbose -O llvm-$(1).tar.xz https://github.com/llvm/llvm-project/releases/download/llvmorg-$(1)/clang+llvm-$(1)-powerpc64le-linux-rhel-$(2).tar.xz
	tar -xf llvm-$(1).tar.xz
	touch $$@
	rm -rf llvm-$(1).tar.xz llvm-$(1)
	mv clang+llvm-* llvm-$(1)

CLEAN_DIRS += llvm-$(1)
ALL_TARGETS += llvm-$(1)
endef

$(eval $(call TEMPLATE,14.0.6,8.4))
$(eval $(call TEMPLATE,15.0.7,8.4))
$(eval $(call TEMPLATE,16.0.6,8.7))
$(eval $(call TEMPLATE,17.0.4,8.8))
$(eval $(call TEMPLATE,18.1.8,8.8))

# Only download clang-18 by default
download: llvm-18.1.8

prepare: download

download-all: $(ALL_TARGETS)

build:

clean:
	@:

distclean: clean
	rm -rf $(CLEAN_DIRS) *.tar.xz

.PHONY: download prepare build clean distclean help
