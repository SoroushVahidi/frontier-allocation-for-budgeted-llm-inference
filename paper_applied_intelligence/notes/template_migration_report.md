# Official Springer Nature template migration report

## Checked official sources

- Springer Nature LaTeX author support: `https://www.springernature.com/gp/authors/campaigns/latex-author-support`
- Springer Nature MLJ submission guidelines: `https://link.springer.com/journal/10994/submission-guidelines`
- Springer Nature Overleaf support article: `https://support.springernature.com/en/support/solutions/articles/6000127538-submit-a-latex-manuscript-to-a-springer-nature-journal-using-overleaf`
- Official Overleaf template page: `https://www.overleaf.com/latex/templates/springer-nature-latex-template/gsvvftmrppwq`

## What I could verify

- The official Springer support page links to the Overleaf gallery template.
- The public Overleaf template page identifies the template as the official Springer Nature LaTeX Template.
- The page metadata shows `sn-article.tex` as the main file and `sn-jnl` as the class family.
- MLJ submission guidelines require a 1-2 page MLJ Contribution Information Sheet.

## What failed

- The template cannot be opened as a new Overleaf project in this environment because the `project/new/template/...` path redirects to Overleaf login.
- The public Overleaf page does not expose a downloadable ZIP archive or a directly retrievable template source bundle through the accessible HTML.
- Because of that, I could not stage a clean official-template manuscript or compile it locally without relying on non-official or unauthenticated sources.

## Conclusion

Manual verification is still required in an authenticated Overleaf session or via an official Springer download path that exposes the template package. The current working `paper_ml_journal/` manuscript was left untouched.
