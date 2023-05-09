vimdiff <(grep "booktitle" $1 | uniq | nl) <(grep "booktitle" abbr.bib | uniq | nl)
