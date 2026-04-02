# uofithesis.cwl
# TeXstudio completion word list for the University of Illinois thesis/dissertation class.
# Encoding: UTF-8

# --- Document class ---
# Provide a convenience snippet for the master's thesis mode.
\documentclass[thesis]{uofithesis}#n
\documentclass{uofithesis}#n

# --- Title page metadata (preamble) ---
\department{department%text}#n
\concentration{concentration%text}#n
\minor{minor%text}#n
\degreeyear{year}#n
\earneddegree{earned degree%text}#n
\committeetitle{committee title%text}#n
\committee{%
\item %<Member%text%>, %<Role%text%>%
%|%
}#n

# --- Optional pages ---
\copyrightpage#n
\chapterreferences#n
\begin{sectionwithreferences}{title%text}#beginEnv#sectionwithreferences
\end{sectionwithreferences}#endEnv#sectionwithreferences

# --- Front matter blocks (command form used by thesis.tex) ---
\abstract{abstract%text}#n
\acknowledgements{acknowledgements%text}#n

# --- Front matter blocks (environment form, also supported) ---
\begin{acknowledgements}#beginEnv#acknowledgements
\end{acknowledgements}#endEnv#acknowledgements

# Note: abstract is a standard LaTeX environment, but is customized by the class.
\begin{abstract}#beginEnv#abstract
\end{abstract}#endEnv#abstract
