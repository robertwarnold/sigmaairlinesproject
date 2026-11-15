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
  })
})
