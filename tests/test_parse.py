"""Round-trip tests: an AI-generated LaTeX body must survive the trip through
the canvas and back, so the user can edit what the model wrote."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web.core import parse_latex_body, render_body
from resumetex_web.core.gallery import preset

AI_BODY = r"""
\section{Professional Summary}
\small{Data analyst with 5+ years of experience turning product data into decisions. Skilled in SQL, Python and Power BI.}

\section{Skills}
\textbf{Languages:} Python, SQL, R\\
\textbf{Frameworks:} Pandas, Airflow\\
\textbf{Cloud and Data:} Power BI, PostgreSQL

\section{Professional Experience}
\textbf{Data Analyst, Infosys} \hfill 2022 - Present\\
\textit{Bengaluru, India}\\
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item Built a Power BI dashboard used by 300 people, cutting reporting time by 30\%.
\item Automated 12 monthly reports with Python, saving 40 hours a month.
\end{itemize}

\textbf{Data Analyst Intern, Persistent Systems} \hfill 2020 - 2022\\
\textit{Pune, India}\\
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item Cleaned 1M+ records in Python, improving data quality by 35\%.
\end{itemize}

\section{Projects}
\textbf{Demand Forecast Pipeline} \hfill 2023\\
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item Built an hourly forecasting pipeline that reduced stock-outs by 18\%.
\end{itemize}

\section{Education}
\textbf{B.Tech Computer Science, RGPV University} \hfill 2016 - 2020\\
\textit{Bhopal, India}\\
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item CGPA 8.4/10.0
\end{itemize}

\section{Achievements}
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item Winner, inter-college analytics hackathon (2023)
\end{itemize}

\section{Languages}
English (Fluent), Hindi (Native)
"""


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.data = parse_latex_body(AI_BODY)

    def test_summary_is_extracted(self):
        self.assertIn("Data analyst with 5+ years", self.data["summary"])
        self.assertNotIn("\\small", self.data["summary"])

    def test_skill_groups_are_extracted(self):
        labels = [group["label"] for group in self.data["skills"]]
        self.assertIn("Languages", labels)
        self.assertIn("Frameworks", labels)
        first = self.data["skills"][0]
        self.assertEqual(first["label"], "Languages")
        self.assertIn("Python", first["items"])

    def test_experience_entries_are_extracted(self):
        entries = self.data["experience"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["role"], "Data Analyst")
        self.assertEqual(entries[0]["company"], "Infosys")
        self.assertEqual(entries[0]["dates"], "2022 - Present")
        self.assertEqual(entries[0]["location"], "Bengaluru, India")
        self.assertEqual(len(entries[0]["bullets"]), 2)
        self.assertIn("30%", entries[0]["bullets"][0])

    def test_projects_and_education_are_extracted(self):
        self.assertEqual(len(self.data["projects"]), 1)
        self.assertEqual(self.data["projects"][0]["role"], "Demand Forecast Pipeline")
        self.assertEqual(len(self.data["education"]), 1)
        self.assertEqual(self.data["education"][0]["company"], "RGPV University")
        self.assertEqual(self.data["education"][0]["bullets"], ["CGPA 8.4/10.0"])

    def test_achievements_and_languages(self):
        self.assertEqual(len(self.data["achievements"]), 1)
        self.assertIn("English (Fluent)", self.data["languages"])

    def test_round_trip_keeps_the_content(self):
        """Canvas -> LaTeX -> canvas must not lose anything."""
        rendered = render_body(self.data, preset("ats-navy"))
        again = parse_latex_body(rendered)
        self.assertEqual(again["summary"], self.data["summary"])
        self.assertEqual(len(again["experience"]), len(self.data["experience"]))
        self.assertEqual(again["experience"][0]["role"], self.data["experience"][0]["role"])
        self.assertEqual(again["experience"][0]["dates"], self.data["experience"][0]["dates"])
        self.assertEqual(again["experience"][0]["bullets"], self.data["experience"][0]["bullets"])
        self.assertEqual(len(again["skills"]), len(self.data["skills"]))
        self.assertEqual(again["skills"][0]["items"], self.data["skills"][0]["items"])
        self.assertEqual(again["education"][0]["company"], self.data["education"][0]["company"])

    def test_empty_body_is_safe(self):
        data = parse_latex_body("")
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["experience"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
