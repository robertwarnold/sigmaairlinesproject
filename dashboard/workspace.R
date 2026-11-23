# UI projection of an existing experiment manifest. No quality statistics calculated.
read_workspace_plan <- function(path) {
  tryCatch({
    p <- jsonlite::fromJSON(path); r <- as_table(p$runs)
    stopifnot(nrow(r)>0,all(c('run_id','system','skill_version') %in% names(r)),
      !anyDuplicated(r$run_id),all(r$system %in% LETTERS[1:5]),all(r$skill_version=='v4.0'))
    list(runs=r,status=p$condition_status,path=basename(path))
  },error=function(e) list(runs=data.frame(),status='Experiment manifest unavailable',path=NULL))
}
workspace_progress <- function(d,plan) {
  registry <- as_table(d$registry); planned <- plan$runs
  htmltools::tagList(htmltools::div(class='progress-header',htmltools::span('System'),htmltools::span('Planned'),htmltools::span('Generated'),htmltools::span('Evaluated')),
    lapply(LETTERS[1:5],function(system) {
      ids <- planned$run_id[planned$system==system]
      records <- if(nrow(registry) && length(ids)) registry[registry$run_id %in% ids & registry$system==system & registry$skill_version=='v4.0',,drop=FALSE] else data.frame()
      # Display exact distinct receipt identities; retries do not create replicates.
      generated <- if(nrow(records)) length(unique(records$run_id[records$generation_status=='success'])) else 0
      evaluated <- if(nrow(records)) length(unique(records$run_id[records$evaluation_status=='evaluated'])) else 0
      htmltools::div(class='progress-system',htmltools::strong(system),htmltools::span(if(nrow(planned)) length(ids) else 'Unknown'),
        htmltools::span(if(nrow(planned)) generated else 'Unknown'),htmltools::span(if(nrow(planned)) evaluated else 'Unknown'))
    }),htmltools::tags$p(class='chart-note',if(nrow(planned)) 'Exact manifest run IDs only. Historical receipts are not Round 2 replicates.' else 'Load a manifest to show experiment progress.'),
    htmltools::tags$details(class='chart-details',htmltools::tags$summary('Plan readiness'),htmltools::tags$p(plan$status)))
}
method_section <- function(title,summary,detail=NULL) htmltools::tags$section(class='method-section',
  htmltools::tags$h2(title),htmltools::tags$p(summary),
  if(!is.null(detail)) htmltools::tags$details(htmltools::tags$summary('Details'),detail))
