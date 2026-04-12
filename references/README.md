# References

This directory is for tracking papers, notes, and citation management for the project.

---

## How References Are Tracked

Papers and references are managed as follows:

1. **Paper notes**: Add a short markdown file per paper under `references/papers/` with the format `AuthorYear_ShortTitle.md`. Include: citation, abstract summary, key findings, and relevance to this project.

2. **BibTeX file**: Maintain a single `references/references.bib` file for all citations used in the paper draft.

3. **Related work notes**: High-level synthesis and comparison notes go in `docs/related_work.md`.

---

## Directory Layout (Planned)

```
references/
├── README.md               # This file
├── references.bib          # BibTeX citations (to be created)
└── papers/                 # Per-paper notes (to be populated)
    └── ExampleAuthor2024_ShortTitle.md
```

---

## Template for Paper Notes

```markdown
# [Author(s), Year] Title

**Venue:** ...
**Link:** ...

## Summary
...

## Key Results
- ...

## Relevance to This Project
...

## Open Questions
...
```

---

## TODO

- [ ] Add BibTeX entries for all papers in the literature review checklist (`docs/research_plan.md`).
- [ ] Create a note for each reviewed paper under `references/papers/`.
