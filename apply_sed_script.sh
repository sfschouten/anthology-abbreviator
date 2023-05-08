#!/bin/bash
LINES=$(wc -l $1 | cut -d' ' -f1)
echo "$1 has $LINES lines."
sed -E -f abbreviate.sed $1 | (pv -l -s $LINES > abbr.bib)
