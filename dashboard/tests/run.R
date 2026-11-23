# Run from the project root: Rscript dashboard/tests/run.R
source('dashboard/bootstrap.R'); source('dashboard/data.R'); source('dashboard/plots.R'); source('dashboard/poster.R')
library(testthat)

test_that('workspace routes and shared global filters preserve selection semantics', {
  library(shiny);library(bslib)
  source('dashboard/charts.R');source('dashboard/engineering.R');source('dashboard/single_page.R');source('dashboard/analytics.R')
  defaults<-jsonlite::fromJSON('dashboard/data/financial-defaults.json')
  html<-as.character(analytics_ui(defaults))
  expect_match(html,'FMEA Engineering Intelligence',fixed=TRUE)
  for(view in names(workspace_views)) expect_match(html,paste0('href="#',view,'"'),fixed=TRUE)
  expect_match(html,'executive_metrics',fixed=TRUE)
  expect_match(html,'id="fmea-register"',fixed=TRUE)
  expect_match(html,'analytics_health',fixed=TRUE)
  rows<-data.frame(record_id=c('one','two'),run_id=c('r1','r2'),system=c('A','B'),subsystem=c('s1','s2'),
    generator_model=c('m1','m2'),skill_version='v4.0',review_status=c('NEEDS_REVIEW','APPROVED'),severity=c(9,3),occurrence=c(1,2),
    generation_timestamp=c('2026-11-15','2026-11-14'),component=c('Synthetic MOTOR','Synthetic valve'))
  expect_equal(filter_engineering_rows(rows,list(system='A'))$record_id,'one')
  expect_equal(filter_engineering_rows(rows,list(model='m2',review='APPROVED'))$record_id,'two')
  expect_equal(nrow(filter_engineering_rows(rows,list(system='A',subsystem='s2'))),0)
  expect_equal(filter_engineering_rows(rows,list(),search='motor')$record_id,'one')
  expect_equal(filter_engineering_rows(rows,list(dates=as.Date(c('2026-11-15','2026-11-15'))))$record_id,'one')
  expect_equal(filter_engineering_rows(rows,list(),focus='two')$record_id,'two')
  expect_equal(nrow(filter_generation_rows(rows,list(review='APPROVED'))),0)
  expect_equal(filter_generation_rows(rows,list(system='B'))$run_id,'r2')
  matrix<-as.character(engineering_matrix_chart(data.frame(severity=9,occurrence=1,count=2)))
  expect_match(matrix,'Severity 9, occurrence 1: 2 rows',fixed=TRUE)
  expect_match(matrix,'not a formal risk acceptance',fixed=TRUE)
})

test_that('experiment identity uses structured evidence and flags conflicts', {
  source('dashboard/experiment_identity.R')
  mapping <- jsonlite::fromJSON('dashboard/data/experiment-mappings.json',simplifyVector=FALSE)
  resolved <- experiment_identity(list(run_id='stable',original_filename='system_a_round2_run03.json'),mapping=mapping)
  expect_equal(resolved$label,'System A \u00b7 Round 2 \u00b7 Run 03')
  expect_equal(resolved$id,'stable')
  expect_equal(experiment_identity(list(run_id='system_b_v4.0_run02.csv'),mapping=mapping)$label,
    'System B \u00b7 Round unverified \u00b7 Run 02')
  expect_equal(experiment_identity(list(run_id='legacy:system_c_v2.0_run01'),mapping=mapping)$label,
    'System C \u00b7 Round unverified \u00b7 Run 01')
  expect_equal(experiment_identity(list(run_id='round2-A-r03',manifest_round=3),mapping=mapping)$round,'3')
  expect_equal(generation_duration_label(61),'1 min 01 s')
  expect_equal(generation_duration_label(3720),'1 h 02 min')
  expect_equal(generation_duration_label(NA_real_),'Unavailable')
  conflicting <- experiment_identity(list(system='B',run_id='round2-A-r03'),mapping=mapping)
  expect_equal(conflicting$conflicts,'system')
  expect_equal(conflicting$system,'B')
})

test_that('historical scope shares source denominators across views and exports', {
  source('dashboard/scope.R')
  archive <- list(schema='historical-comparison-1',source_sha256='source',
    metrics=list('v2.0'=list(runs=18),'v3.0'=list(runs=15)),
    metrics_by_system=list(B=list('v2.0'=list(runs=5),'v3.0'=list(runs=3))))
  expect_equal(select_historical_scope(archive,'B',round='2')$metrics,list('v3.0'=list(runs=3)))
  expect_length(select_historical_scope(archive,'B','v2.0','2')$metrics,0)
  expect_equal(select_historical_scope(archive)$source_sha256,'source')
  expect_match(scope_text('B','2','v3.0',NULL,NULL,list(),list()),'System B',fixed=TRUE)
})

test_that('private RPN histogram preserves supplied bins and missing values stay outside', {
  source('dashboard/charts.R'); source('dashboard/engineering.R')
  bins <- data.frame(lower=c(1,101),upper=c(100,200),count=c(2,0))
  chart <- as.character(engineering_rpn_chart(bins))
  expect_match(chart,'RPN 1 to 100 : 2 rows',fixed=TRUE)
  expect_match(chart,'RPN 101 to 200 : 0 rows',fixed=TRUE)
  expect_match(chart,'100-point bins',fixed=TRUE)
  expect_false(grepl('NaN|Infinity',chart))
})
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
source('dashboard/workspace.R')
source('dashboard/engineering.R')
test_that('private workspace requires explicit loopback origin and does not expose public records', {
  request <- list(REMOTE_ADDR='127.0.0.1',HTTP_HOST='127.0.0.1:5393',HTTP_ORIGIN='http://127.0.0.1:5393')
  expect_true(engineering_allowed('1',request))
  expect_false(engineering_allowed('',request)); expect_false(engineering_allowed('1',NULL))
  request$REMOTE_ADDR <- '192.0.2.1'; expect_false(engineering_allowed('1',request))
  request$REMOTE_ADDR <- '127.0.0.1'; request$HTTP_ORIGIN <- 'https://outside.example'; expect_false(engineering_allowed('1',request))
  request$HTTP_ORIGIN <- NULL; request$HTTP_X_FORWARDED_FOR <- '192.0.2.1'; expect_false(engineering_allowed('1',request))
  rows <- data.frame(record_id='synthetic-only',failure_mode='<script>synthetic</script>',severity=NA_real_)
  html <- as.character(engineering_table(rows,c('failure_mode','severity')))
  expect_false(grepl('<script>',html,fixed=TRUE)); expect_match(html,'Unknown')
})
test_that('manifest progress excludes historical aliases and duplicate attempts', {
  d <- list(registry=data.frame(run_id=c('old','planned-A','planned-A'),system='A',skill_version='v4.0',
    generation_status='success',evaluation_status=c('not_evaluated','evaluated','evaluated')))
  plan <- list(runs=data.frame(run_id=c('planned-A','planned-B'),system=c('A','B'),skill_version='v4.0'),status='SYNTHETIC TEST PLAN')
  html <- as.character(workspace_progress(d,plan))
  expect_match(html,'SYNTHETIC TEST PLAN'); expect_match(html,'Exact manifest run IDs only')
  expect_false(grepl('>2</span>',html,fixed=TRUE))
  expect_equal(nrow(read_workspace_plan(tempfile())$runs),0)
})

test_that('accepted synthetic snapshot refresh updates charts and corruption retains last good', {
  d <- read_snapshot('dashboard/data/baseline.json'); path <- tempfile(fileext='.json')
  save <- function(value) jsonlite::write_json(value,path,auto_unbox=TRUE,dataframe='rows',null='null')
  save(d); previous <- getwd(); setwd('dashboard'); on.exit(setwd(previous),add=TRUE)
  env <- new.env(parent=globalenv()); sys.source('app.R',envir=env); env$source_path <- path
  shiny::testServer(env$server, {
    session$setInputs(refresh=1,versions='v4.0',systems='A',eval_status='All',dates=c('2026-01-01','2026-12-31'))
    session$flushReact(); expect_match(output$run_plot$html,'Awaiting independent evaluation')
    d$runs <- data.frame(run_id='SYNTHETIC-REFRESH',system='A',skill_version='v4.0',missed_percentage=17,
      generated_rows=30,found=20,missed=4,extra_unmatched_rows=1)
    d$last_updated <- '2026-11-17T00:00:00+00:00'; save(d)
    session$setInputs(refresh=2); session$elapse(30010); session$flushReact()
    expect_equal(nrow(data()$runs),1); expect_match(output$run_plot$html,'SYNTHETIC-REFRESH')
    writeLines('{broken',path); session$setInputs(refresh=3); session$elapse(30010); session$flushReact()
    expect_match(output$run_plot$html,'SYNTHETIC-REFRESH')
  })
})
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
    expect_match(output$mission_kpis$html,'Pending')
    expect_false(grepl('31.4',output$mission_kpis$html,fixed=TRUE))
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
