%% svjour3.cls — minimal compatibility stub for local/tectonic compilation.
%% Overleaf provides the full Springer class automatically; this stub is only
%% needed for local builds where the official Springer class is unavailable.
%% Replace with the official svjour3.cls from the Springer Author Kit for
%% final Springer submission.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{svjour3}[2024/01/01 Springer Journal 3 stub]

%% Accept and ignore all class options
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax

\LoadClass[11pt,a4paper]{article}

%% ---- Page geometry ----
\RequirePackage[a4paper,
  top=25mm, bottom=25mm, left=25mm, right=25mm,
  headheight=14pt]{geometry}

%% ---- Standard packages assumed by Springer template ----
\RequirePackage{amsmath,amssymb}
\RequirePackage{graphicx}

%% ---- Journal name ----
\newcommand{\journalname}[1]{\def\@journalname{#1}}
\journalname{}

%% ---- \smartqed: Springer's "smart" QED symbol placement ----
\newcommand{\smartqed}{}   % no-op in stub; proof env handled by amsthm if loaded

%% ---- \institute / \at / \email ----
% \institute replaces the standard \address in Springer style.
% In article class we store it and typeset it after \maketitle.
\newcommand{\at}{\unskip,\ }
\newcommand{\email}[1]{\texttt{#1}}
\newcommand{\institute}[1]{\def\@institute{#1}}
\institute{}

%% Patch \maketitle to append institute block
\let\sv@maketitle\maketitle
\renewcommand{\maketitle}{%
  \sv@maketitle
  \ifx\@institute\@empty\else
    \begin{center}
      \small\@institute
    \end{center}
    \vskip 0.5em
  \fi
}

%% ---- \keywords ----
\newcommand{\keywords}[1]{%
  \par\vskip 0.5em
  \noindent\textbf{Keywords:} #1\par\vskip 0.5em
}

%% ---- \and in \author already defined by article class ----

%% ---- Line-breaking tolerance (avoids minor body-text overfull hboxes) ----
\AtBeginDocument{\setlength{\emergencystretch}{2.5em}}

%% ---- section formatting (approximate Springer look) ----
\RequirePackage{titlesec}
\titleformat{\section}{\normalfont\large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}{\normalfont\normalsize\bfseries}{\thesubsection}{1em}{}
\titleformat{\subsubsection}{\normalfont\normalsize\itshape}{\thesubsubsection}{1em}{}

%% ---- Theorem-like environments (Springer defines these) ----
\RequirePackage{amsthm}
\newtheorem{theorem}{Theorem}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{proposition}[theorem]{Proposition}
\theoremstyle{definition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{example}[theorem]{Example}
\theoremstyle{remark}
\newtheorem{remark}[theorem]{Remark}

\endinput
