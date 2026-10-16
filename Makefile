LMS_DIR  := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
BASHRC   ?= $(HOME)/.bashrc
BEGIN    := \# >>> yocto-lms >>>
END      := \# <<< yocto-lms <<<

.PHONY: install uninstall

# Add (or refresh) a marked block in ~/.bashrc that sources lms.sh.
install: uninstall
	@touch "$(BASHRC)"
	@printf '%s\n' '$(BEGIN)' 'source "$(LMS_DIR)lms.sh"' '$(END)' >> "$(BASHRC)"
	@echo "Installed into $(BASHRC). Run: source $(BASHRC)"

uninstall:
	@if [ -f "$(BASHRC)" ]; then \
		sed -i '/^$(BEGIN)$$/,/^$(END)$$/d' "$(BASHRC)"; \
	fi
