# Rendering benchmark only; no research metrics are recalculated.
# Rscript dashboard/benchmark.R snapshot.json output.json
source('dashboard/bootstrap.R'); source('dashboard/data.R'); source('dashboard/plots.R'); source('dashboard/charts.R')
args <- commandArgs(trailingOnly=TRUE); stopifnot(length(args)==2)
d <- read_snapshot(args[1]); f <- d$financial
cases <- list(activity=function() dashboard_activity(d),versions=function() dashboard_versions(d),
  runs=function() dashboard_runs(d),pareto=function() dashboard_pareto(d),agreement=function() dashboard_agreement(d),
  finance=function() dashboard_finance(f,'simulation'))
results <- lapply(names(cases),function(name) {
  times <- replicate(5,system.time(html <- as.character(cases[[name]]()))[['elapsed']])
  list(component=name,median_ms=median(times)*1000,max_ms=max(times)*1000,html_bytes=nchar(as.character(cases[[name]]()),type='bytes'))
})
dir.create(dirname(args[2]),recursive=TRUE,showWarnings=FALSE)
jsonlite::write_json(list(snapshot=d$data_version,method='Five warm R HTML/SVG construction samples; not browser latency or model runtime',components=results),args[2],auto_unbox=TRUE,pretty=TRUE)
