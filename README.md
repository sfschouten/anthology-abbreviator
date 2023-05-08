# Anthology Abbreviator

My attempt at automatically generating a version of the ACL anthology with abbreviated proceedings titles.

WORK IN PROGRESS

## Method
We try our best to determine a good acronym for all proceedings.

Process each proceedings:
  - If proceedings is only one that year for its venue, use f"{venue-acronym} {year}"
  - If proceedings is not alone in its year
    - Look for name of venue(s) in proceedings title
