LATEXMK ?= latexmk
MAIN    := main

.PHONY: all pdf clean veryclean

all: pdf

pdf:
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error $(MAIN).tex

clean:
	$(LATEXMK) -c

veryclean:
	$(LATEXMK) -C
	rm -f $(MAIN).bbl $(MAIN).blg
