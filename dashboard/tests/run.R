# Run from the project root: Rscript dashboard/tests/run.R
source('dashboard/bootstrap.R'); source('dashboard/data.R'); source('dashboard/plots.R'); source('dashboard/poster.R')
library(testthat)
test_that('baseline is explicit and missing versions remain pending', {
  d <- read_snapshot('dashboard/data/baseline.json')
  expect_equal(nrow(as_table(d$runs)),0)
  expect_equal(d$statistics$criteria$mean_below_20,'PENDING')
  expect_equal(d$research_status,'REPORT_DERIVED_BASELINE_ONLY')
  expect_s3_class(coverage_plot(d),'ggplot')
  expect_s3_class(pareto_plot(d),'ggplot')
})
test_that('refresh accepts valid changes and rejects corruption while retaining cache', {
  d <- read_snapshot('dashboard/data/baseline.json'); source <- tempfile(); cache <- tempfile()
  jsonlite::write_json(d,source,auto_unbox=TRUE,null='null')
  loader <- make_loader(source,'dashboard/data/baseline.json',cache)
  first <- loader(); expect_equal(first$data$data_version,d$data_version)
  d$last_updated <- '2026-11-16T00:00:00+00:00'
  jsonlite::write_json(d,source,auto_unbox=TRUE,null='null')
  expect_equal(loader()$data$last_updated,d$last_updated)
  writeLines('{broken',source)
  expect_equal(loader()$data$last_updated,d$last_updated)
  unlink(source)
  expect_match(loader()$status,'last known good')
})
test_that('poster export and both ggplots produce standalone artifacts', {
  d <- read_snapshot('dashboard/data/baseline.json'); folder <- tempfile(); dir.create(folder)
  poster_export(d,file.path(folder,'poster.pdf'))
  expect_gt(file.info(file.path(folder,'poster.pdf'))$size,1000)
  for(name in c('coverage','pareto')) {
    p <- if(name=='coverage') coverage_plot(d) else pareto_plot(d)
    ggsave(file.path(folder,paste0(name,'.png')),p,width=8,height=4,dpi=100)
    expect_gt(file.info(file.path(folder,paste0(name,'.png')))$size,1000)
  }
})
cat('Dashboard R checks completed\n')

source('dashboard/charts.R')
test_that('dashboard components preserve validated data and separate pending evidence', {
  d <- read_snapshot('dashboard/data/baseline.json'); original <- serialize(d,NULL)
  pending <- as.character(dashboard_versions(d))
  expect_match(pending,'Awaiting independent evaluation')
  expect_match(pending,'Historical V2 baseline')
  expect_false(grepl('native-bar-row|0 evaluated FMEAs',pending))
  expect_match(as.character(dashboard_runs(d)),'Awaiting independent evaluation')
  expect_match(as.character(dashboard_pareto(d)),'114')
  expect_match(as.character(dashboard_pareto(d)),'49.1')
  expect_match(as.character(dashboard_agreement(d)),'within \u00b11')
  expect_match(as.character(dashboard_agreement(d)),'within 25%')
  expect_identical(serialize(d,NULL),original)
})

test_that('synthetic evaluated chart marks retain identity, supplied rates and intervals', {
  d <- read_snapshot('dashboard/data/baseline.json')
  d$runs <- data.frame(run_id='SYNTHETIC-<script>',system='A',skill_version='v4.0',missed_percentage=17,generated_rows=30)
  d$per_version <- data.frame(skill_version='v4.0',system_weighted_mean=17,mean_run_missed_percentage=19,runs=4,ci_low=12,ci_high=23)
  original <- serialize(d,NULL)
  r <- as.character(dashboard_runs(d)); v <- as.character(dashboard_versions(d))
  expect_match(r,'17% missed'); expect_match(r,'data-run=')
  expect_false(grepl('<script>',r,fixed=TRUE))
  expect_match(v,'17%'); expect_match(v,'n = 4'); expect_match(v,'12 to 23')
  expect_identical(serialize(d,NULL),original)
  expect_match(as.character(dashboard_runs(d,scatter=TRUE)),'30 generated rows')
})

test_that('synthetic financial graphics preserve loss and unknown spending', {
  f <- list(modeled=list(manual_annual_cost=100,ai_annual_operating_cost=200),
    simulation=list(histogram=data.frame(midpoint=c(-200,0,200),count=c(2,5,3)),
      median_annual_net_savings=-40,interval95_annual_usd=c(-220,120)),
    observed_spending=data.frame(generation_timestamp='2026-11-01T00:00:00',known_billed_subtotal=NA_real_),
    activities=data.frame(activity='Synthetic review',cost_per_fmea=20),
    sensitivity=data.frame(assumption='labor_rate',low=-300,high=100),version_review_costs=list())
  original <- serialize(f,NULL)
  expect_match(as.character(dashboard_finance(f,'simulation')),'-220')
  expect_match(as.character(dashboard_finance(f,'simulation')),'simulation interval')
  expect_match(as.character(dashboard_finance(f,'spending')),'Actual spending unknown')
  for(kind in c('comparison','simulation','breakdown','sensitivity','spending','versions'))
    expect_gt(nchar(as.character(dashboard_finance(f,kind))),40)
  expect_identical(serialize(f,NULL),original)
})

test_that('synthetic run selection exposes only a matching accepted run', {
  d <- read_snapshot('dashboard/data/baseline.json')
  d$runs <- data.frame(run_id='SYNTHETIC-SELECT',system='A',skill_version='v4.0',
    missed_percentage=17,generated_rows=30,found=20,missed=4,extra_unmatched_rows=1)
  path <- tempfile(fileext='.json'); jsonlite::write_json(d,path,auto_unbox=TRUE,dataframe='rows',null='null')
  previous <- getwd(); setwd('dashboard'); on.exit(setwd(previous),add=TRUE)
  env <- new.env(parent=globalenv()); sys.source('app.R',envir=env); env$source_path <- path
  shiny::testServer(env$server, {
    session$setInputs(refresh=1,versions='v4.0',systems='A',eval_status='All',dates=c('2026-01-01','2026-12-31'))
    session$flushReact()
    expect_match(output$run_plot$html,'SYNTHETIC-SELECT')
    session$setInputs(chart_run='SYNTHETIC-SELECT'); session$flushReact()
    expect_match(output$selected_chart_run$html,'SYNTHETIC-SELECT')
    session$setInputs(chart_run='OTHER-RUN'); session$flushReact()
    expect_true(is.null(output$selected_chart_run$html) || !nzchar(output$selected_chart_run$html))
  })
})
test_that('Shiny server starts and renders baseline-only outputs without keys', {
  previous <- getwd(); setwd('dashboard'); on.exit(setwd(previous), add = TRUE)
  app_env <- new.env(parent = globalenv())
  sys.source('app.R', envir = app_env)
  app_env$source_path <- normalizePath('data/baseline.json')
  shiny::testServer(app_env$server, {
    session$setInputs(refresh=1,versions=c('v2.0','v3.0','v4.0'),systems=LETTERS[1:5],run='All',eval_status='All',dates=c('2026-01-01','2026-12-31'))
    session$flushReact()
    expect_equal(data()$schema,'sigma-dashboard-4')
    expect_match(output$evidence_status,'REPORT_DERIVED_BASELINE_ONLY')
    expect_equal(nrow(filtered()),0)
    expect_match(output$poster_results$html,'Pending Evaluation')
    expect_match(output$mission_quality$html,'Historical V2 baseline')
    expect_match(output$run_plot$html,'Awaiting independent evaluation')
    expect_match(output$quality_accuracy$html,'within 25%')
    expect_match(output$pareto_detail$html,'114')
  })
})
test_that('financial scenarios use Python, retain negative savings and reset defaults', {
  previous <- getwd(); setwd('dashboard'); on.exit(setwd(previous),add=TRUE)
  env <- new.env(parent=globalenv()); sys.source('app.R',envir=env)
  env$source_path <- normalizePath('data/baseline.json')
  shiny::testServer(env$server, {
    session$setInputs(refresh=1,versions=c('v2.0','v3.0','v3.0-audit','v4.0'),systems=LETTERS[1:5],run='All',eval_status='All',dates=c('2026-01-01','2026-12-31'))
    session$flushReact(); session$elapse(1000)
    base <- financial_result()$data
    expect_equal(base$status,'MODELED_NOT_MEASURED')
    expect_null(base$measured$actual_api_spending)
    session$setInputs(fin_missed_reconstruction_minutes=300); session$elapse(1000); session$flushReact()
    loss <- financial_result()$data
    expect_lt(loss$modeled$first_year_net_savings,0)
    session$setInputs(fin_missed_reconstruction_minutes=env$financial_defaults$missed_reconstruction_minutes,reset_finance=1)
    session$elapse(1000); session$flushReact()
    expect_equal(financial_result()$data$modeled$first_year_net_savings,base$modeled$first_year_net_savings)
    expect_equal(nrow(as_table(data()$runs)),0)
  })
})
test_that('4.1 reader rejects premature quality and figures handle synthetic evaluated data', {
  d <- read_snapshot('dashboard/data/baseline.json')
  d$schema <- 'sigma-dashboard-4.1'
  for(name in c('workflow_executions','evaluations','lifecycle_events','financial','field_accuracy')) d[[name]] <- list()
  d$operations <- list(evaluated_fmeas=0)
  d$financial <- list(status='MODELED_NOT_MEASURED',measured=list())
  d$registry <- data.frame(generation_id='synthetic-only',system='A',skill_version='v4.0',generation_status='success',evaluation_status='awaiting_evaluation',missed_percentage=NA_real_)
  expect_equal(validate_snapshot(d)$schema,'sigma-dashboard-4.1')
  d$registry$missed_percentage <- 12
  expect_error(validate_snapshot(d))
  d <- read_snapshot('dashboard/data/baseline.json')
  d$research_status <- 'SYNTHETIC_TEST_ONLY'
  d$runs <- data.frame(run_id='SYNTHETIC-ONLY',system='A',skill_version='v4.0',missed_percentage=10,generated_rows=20)
  expect_s3_class(coverage_plot(d),'ggplot')
  expect_s3_class(completeness_plot(d),'ggplot')
  expect_s3_class(field_accuracy_plot(d),'ggplot')
})
