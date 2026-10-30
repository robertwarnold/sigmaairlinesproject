source('fmea_generator.R')

# Pilot first: set n_runs <- 1; full baseline: n_runs <- 25
n_runs <- 1
systems <- data.frame(
  case_id = paste0('system_', 1:4),
  path = file.path('system_descriptions', paste0('system_', 1:4, '.txt'))
)

log_file <- file.path('results', 'run_log.csv')
dir.create('results', showWarnings = FALSE)

for (i in seq_len(nrow(systems))) {
  for (r in seq_len(n_runs)) {
    case_id <- systems$case_id[i]
    cat('Running', case_id, 'replication', r, '\n')
    status <- 'success'
    error_message <- ''
    tryCatch({
      generate_fmea(systems$path[i], case_id, run = r)
    }, error = function(e) {
      status <<- 'error'
      error_message <<- conditionMessage(e)
      message('FAILED: ', error_message)
    })
    log_row <- data.frame(case_id = case_id, version = PROMPT_VERSION,
                          run = r, status = status, error = error_message)
    if (file.exists(log_file)) {
      write.table(log_row, log_file, append = TRUE, sep = ',',
                  col.names = FALSE, row.names = FALSE, quote = TRUE)
    } else {
      write.csv(log_row, log_file, row.names = FALSE)
    }
    Sys.sleep(1) # adjust for your API limits
  }
}

# Combine successfully parsed FMEA CSVs (not raw text or run_log)
files <- list.files('results', pattern = '^system_[1-4]_v[0-9.]+_run[0-9]+\\.csv$',
                    full.names = TRUE)
if (length(files)) {
  combined <- dplyr::bind_rows(lapply(files, readr::read_csv, show_col_types = FALSE))
  readr::write_csv(combined, 'results/all_generated_fmeas.csv')
}
