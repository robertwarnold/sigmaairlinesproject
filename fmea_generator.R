# Sigma Airlines FMEA Generator v1.0
# Requires: install.packages(c('httr2','jsonlite','dplyr','readr'))
library(httr2)
library(jsonlite)
library(dplyr)
library(readr)

MODEL <- Sys.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5') # Set to a model available to your account
PROMPT_VERSION <- 'v1.0'

fmea_instructions <- paste(
  'You are an engineering FMEA drafting assistant, not an approval authority.',
  'Analyze ONLY the supplied system description, functions, interfaces and requirements.',
  'Identify plausible component/function failure modes, causes, local effects, system effects, and specific recommended actions.',
  'Do not invent evidence, failure frequencies, requirements or reference FMEA content.',
  'For each row, estimate Severity, Occurrence and Detection on the supplied 1-10 rubric.',
  'Severity: 1 negligible consequence; 10 catastrophic consequence.',
  'Occurrence: 1 very unlikely; 10 very frequent. If frequency data are absent, use an explicitly provisional engineering judgment.',
  'Detection: 1 very likely to detect before impact; 10 very unlikely to detect.',
  'Scores are provisional, not validated failure probabilities. Include a rationale and uncertainty flag.',
  'Consider complete, partial, intermittent, degraded and unintended operation where applicable.',
  'Do not see or infer a hidden ground-truth FMEA. Do not produce fault trees.',
  'Return ONLY a JSON array of objects. Each object must contain these keys:',
  'component, function, failure_mode, cause, local_effect, system_effect,',
  'recommended_action, severity, occurrence, detection, rating_rationale, evidence, review_flag.',
  'Use numeric integers 1-10 for the three ratings. Do not include RPN: R calculates it.',
  sep='\n'
)

call_claude <- function(system_text, model = MODEL, max_tokens = 8192) {
  api_key <- Sys.getenv('ANTHROPIC_API_KEY')
  if (!nzchar(api_key)) stop('ANTHROPIC_API_KEY is missing from environment')
  response <- request('https://api.anthropic.com/v1/messages') |>
    req_headers(
      'x-api-key' = api_key,
      'anthropic-version' = '2023-06-01',
      'content-type' = 'application/json'
    ) |>
    req_body_json(list(
      model = model,
      max_tokens = max_tokens,
      temperature = 0,
      system = fmea_instructions,
      messages = list(list(role = 'user', content = paste('SYSTEM DESCRIPTION:\n', system_text)))
    ), auto_unbox = TRUE) |>
    req_retry(max_tries = 3) |>
    req_perform()
  body <- resp_body_json(response, simplifyVector = FALSE)
  if (!identical(body$stop_reason, 'end_turn')) {
    stop('Model output incomplete (stop_reason: ', body$stop_reason, ')')
  }
  blocks <- Filter(function(x) identical(x$type, 'text'), body$content)
  paste(vapply(blocks, function(x) x$text, character(1)), collapse = '\n')
}

parse_fmea <- function(raw_text) {
  cleaned <- trimws(raw_text)
  cleaned <- sub('^```(?:json)?\\s*', '', cleaned)
  cleaned <- sub('\\s*```$', '', cleaned)
  items <- fromJSON(cleaned, simplifyVector = FALSE)
  if (!is.list(items) || length(items) == 0 || !all(vapply(items, is.list, logical(1)))) {
    stop('Expected a nonempty JSON array of FMEA objects')
  }
  required <- c('component','function','failure_mode','cause','local_effect',
                'system_effect','recommended_action','severity','occurrence',
                'detection','rating_rationale','evidence','review_flag')
  for (item in items) {
    if (!all(required %in% names(item))) stop('FMEA row missing required fields')
    for (field in c('severity','occurrence','detection')) {
      value <- item[[field]]
      if (!is.numeric(value) || length(value) != 1 || is.na(value) ||
          value < 1 || value > 10 || value != as.integer(value)) {
        stop('Invalid rating in ', field)
      }
    }
  }
  rows <- lapply(items, function(item) {
    as.data.frame(item[required], stringsAsFactors = FALSE)
  })
  out <- bind_rows(rows)
  out <- out |> mutate(
    severity = as.integer(severity),
    occurrence = as.integer(occurrence),
    detection = as.integer(detection),
    RPN = severity * occurrence * detection
  )
  out
}

generate_fmea <- function(system_file, case_id, version = PROMPT_VERSION,
                          run = 1, output_dir = 'results', model = MODEL) {
  if (!file.exists(system_file)) stop('Missing system file: ', system_file)
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  system_text <- paste(readLines(system_file, warn = FALSE), collapse = '\n')
  started <- Sys.time()
  raw <- call_claude(system_text, model = model)
  elapsed <- as.numeric(difftime(Sys.time(), started, units = 'mins'))
  prefix <- sprintf('%s_%s_run%02d', case_id, version, run)
  writeLines(raw, file.path(output_dir, paste0(prefix, '_raw.txt')))
  fmea <- parse_fmea(raw) |>
    mutate(case_id = case_id, version = version, run = run,
           model = model, generation_minutes = elapsed, .before = 1)
  write_csv(fmea, file.path(output_dir, paste0(prefix, '.csv')))
  fmea
}
