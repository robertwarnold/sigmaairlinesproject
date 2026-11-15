# Shiny and static exports share this validator and last-known-good data loader.
as_table <- function(x) if (is.data.frame(x)) x else data.frame()
validate_snapshot <- function(x) {
  required <- c('schema','data_version','last_updated','validation_status','research_status',
                'baseline','runs','registry','per_system','per_version','pareto','statistics',
                'review_summary','coverage_summary')
  stopifnot(is.list(x), setequal(names(x), required), identical(x$schema, 'sigma-dashboard-4'),
            identical(x$validation_status, 'VALIDATED'),
            is.character(x$data_version), grepl('^[a-f0-9]{64}$', x$data_version),
            is.character(x$last_updated), length(x$last_updated) == 1)
  stopifnot(is.list(x$baseline), is.numeric(x$baseline$opportunities),
            x$baseline$opportunities > 0, is.numeric(x$baseline$missed),
            x$baseline$missed >= 0, x$baseline$missed <= x$baseline$opportunities,
            is.list(x$statistics), is.list(x$statistics$criteria),
            all(unlist(x$statistics$criteria) %in% c('PASS','FAIL','PENDING','INSUFFICIENT_DATA')))
  for (name in c('per_system','per_version')) {
    table <- as_table(x[[name]])
    if (nrow(table)) stopifnot(all(table$skill_version %in% c('v2.0','v3.0','v4.0')),
      all(is.finite(table$mean_run_missed_percentage)),
      all(table$mean_run_missed_percentage >= 0 & table$mean_run_missed_percentage <= 100))
  }
  pareto <- as_table(x$pareto)
  if (nrow(pareto)) stopifnot(all(c('miss_category','count','percentage','cumulative_percentage') %in% names(pareto)),
    all(pareto$miss_category %in% c('Repeated unit skipped','Sub-case not split out','Part never covered','Wrong failure direction','Unclassified')),
    all(is.finite(pareto$count)),all(pareto$count>=0),all(is.finite(pareto$percentage)),
    all(pareto$percentage>=0 & pareto$percentage<=100),all(pareto$cumulative_percentage>=0 & pareto$cumulative_percentage<=100))
  runs <- as_table(x$runs)
  if (nrow(runs)) {
    stopifnot(all(c('run_id','system','skill_version','missed_percentage') %in% names(runs)),
              !anyDuplicated(runs$run_id), all(runs$system %in% LETTERS[1:5]),
              all(runs$skill_version %in% c('v2.0','v3.0','v4.0')),
              all(is.finite(runs$missed_percentage)),
              all(runs$missed_percentage >= 0 & runs$missed_percentage <= 100))
  }
  x
}
read_snapshot <- function(path) validate_snapshot(jsonlite::fromJSON(path, simplifyVector = TRUE))
make_loader <- function(source, fallback, cache = file.path(tempdir(), 'sigma-last-good.json')) {
  state <- new.env(parent = emptyenv())
  state$data <- if (file.exists(cache)) tryCatch(read_snapshot(cache), error = function(e) read_snapshot(fallback)) else read_snapshot(fallback)
  state$status <- 'Offline report-derived baseline'
  function() {
    tryCatch({
      candidate_path <- source
      if (grepl('^https://', source)) {
        candidate_path <- tempfile(fileext = '.json')
        on.exit(unlink(candidate_path), add = TRUE)
        old <- options(timeout = 10); on.exit(options(old), add = TRUE)
        utils::download.file(source, candidate_path, quiet = TRUE, mode = 'wb')
      }
      candidate <- read_snapshot(candidate_path)
      # Persist only a fully validated snapshot. Keep old data on every exception.
      temp <- tempfile(tmpdir = dirname(cache))
      jsonlite::write_json(candidate, temp, auto_unbox = TRUE, dataframe = 'rows', null = 'null', digits = NA)
      if (.Platform$OS.type == 'windows' && file.exists(cache)) {
        # Copy is a cache operation only; in-memory candidate is already validated.
        file.copy(temp, cache, overwrite = TRUE); unlink(temp)
      } else if (!file.rename(temp, cache)) stop('Cannot persist dashboard cache')
      state$data <- candidate; state$status <- 'Validated snapshot loaded'
    }, error = function(e) { state$status <- 'Update unavailable or invalid; retaining last known good snapshot' })
    list(data = state$data, status = state$status)
  }
}
