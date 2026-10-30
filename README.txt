Sigma Airlines FMEA Generator — R pilot

1. Open RStudio and set working directory to this folder (Project > New Project > Existing Directory).
2. install.packages(c('httr2','jsonlite','dplyr','readr'))
3. Put ANTHROPIC_API_KEY=... in ~/.Renviron and restart RStudio.
4. Set ANTHROPIC_MODEL in environment to a model available on your account, or edit MODEL in fmea_generator.R.
5. Replace system_descriptions/system_1.txt and add system_2.txt to system_4.txt with genuine test descriptions.
6. Run source('fmea_generator.R'); generate_fmea('system_descriptions/system_1.txt','system_1')
7. Then source('run_experiment.R'). First pilot with n_runs=1; change to 25 after validation.

Outputs: individual CSVs, raw model replies, run log, and combined CSV.
No actual ground truth, accuracy, review time, or financial data are included.
For reproducible comparisons, freeze model ID, prompt, rubric, system text and evaluator version.
The skill is not an engineering-approved FMEA and must be reviewed by a qualified expert.
