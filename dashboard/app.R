# Aggregate mode has no private rows. Engineering mode is explicitly loopback-only.
source('bootstrap.R')
source('data.R'); source('plots.R'); source('poster.R'); source('charts.R'); source('workspace.R'); source('engineering.R')
library(shiny); library(bslib)
if(identical(Sys.getenv('SIGMA_ENGINEERING_PRIVATE'),'1')) options(shiny.maxRequestSize=21*1024^2)
source_path <- Sys.getenv('SIGMA_DASHBOARD_DATA', file.path(project_root,'results','research','current.json'))
fallback <- 'data/baseline.json'
plan_path <- Sys.getenv('SIGMA_DASHBOARD_MANIFEST',file.path(project_root,'results','v4','round2-plan','experiment_manifest.json'))
financial_defaults <- jsonlite::fromJSON('data/financial-defaults.json')
source('single_page.R'); source('analytics.R'); source('judge_upload.R'); source('executive.R'); source('experiment_identity.R')
source('scope.R')
experiment_mapping <- jsonlite::fromJSON(Sys.getenv('SIGMA_EXPERIMENT_MAPPINGS','data/experiment-mappings.json'),simplifyVector=FALSE)
ui <- analytics_ui(financial_defaults)

server <- function(input,output,session) {
  loader <- make_loader(source_path,fallback)
  import_revision <- reactiveVal(0)
  judge_upload_server(input,output,session,function() import_revision(import_revision()+1))
  # Poll every 30 seconds and on manual refresh. Loader retains validated cache.
  refresh_key <- reactivePoll(30000,session,
    checkFunc = function() paste(input$refresh, import_revision(), if (file.exists(source_path)) file.info(source_path)$mtime else floor(as.numeric(Sys.time())/30)),
    valueFunc = function() loader())
  data <- reactive(refresh_key()$data)
  historical_path <- file.path(project_root,'results','research','historical-comparison.json')
  historical <- reactivePoll(30000,session,
    checkFunc=function() paste(input$refresh,if(file.exists(historical_path)) file.info(historical_path)$mtime else 'missing'),
    valueFunc=function() {
      if(!file.exists(historical_path)) return(NULL)
      tryCatch(jsonlite::fromJSON(historical_path,simplifyVector=FALSE),error=function(e) NULL)
    })
  historical_metrics <- reactive(select_historical_scope(historical(),scope_value(input$g_system),
    scope_value(input$g_skill),scope_value(input$g_round)))
  output$historical_comparison <- renderTable({
    selection <- historical_metrics()
    if(is.null(selection)) return(data.frame(Status='Historical comparison pending import'))
    metrics <- selection$metrics
    if(!length(metrics)) return(data.frame(Status='No historical evidence for the selected system and skill'))
    do.call(rbind,lapply(names(metrics),function(version) {
      value <- metrics[[version]]
      data.frame(Round=unname(historical_rounds[version]),Skill=version,Runs=value$runs,`Pooled missed`=sprintf('%.1f%%',100*value$pooled_missed_rate),
        `Mean run missed`=sprintf('%.1f%%',100*value$mean_run_missed_rate),
        `Equal-system mean missed`=sprintf('%.1f%%',100*value$equal_system_mean_missed_rate),
        `Unmatched rows per run`=round(value$mean_unmatched_generated_per_run,1),check.names=FALSE)
    }))
  })
  output$historical_export_action <- renderUI({
    if(length(historical_metrics()$metrics)) downloadButton('historical_export','Export historical metrics')
  })
  output$historical_export <- downloadHandler(
    filename=function() 'historical-comparison.csv',
    content=function(file) {
      selection <- historical_metrics()
      req(length(selection$metrics))
      rows <- lapply(names(selection$metrics),function(version) {
        system <- if(is.null(input$g_system)) 'All' else input$g_system
        as.data.frame(c(list(skill=version,round=unname(historical_rounds[version]),system=system,source_sha256=selection$source_sha256),
          selection$metrics[[version]]))
      })
      write.csv(do.call(rbind,rows),file,row.names=FALSE)
    })
  output$evidence_status <- renderText(paste('Evidence:',data()$research_status,'|',refresh_key()$status))
  output$snapshot_status <- renderText(paste('Study data as of',data()$last_updated,'| Snapshot',substr(data()$data_version,1,12),'|',data()$validation_status))
  output$poster_results <- renderUI({
    d <- data(); versions <- as_table(d$per_version); v4 <- if (nrow(versions)) versions[versions$skill_version=='v4.0',,drop=FALSE] else data.frame()
    delta <- d$statistics$confidence_intervals$improvement
    tagList(p(strong(paste0('V2 reported pooled missed rate: ',d$baseline$pooled_missed_percentage_reported,'%'))),
      p(if (nrow(v4)) sprintf('V4 run mean missed rate: %.1f%% (%d evaluated runs)',v4$mean_run_missed_percentage[1],v4$runs[1]) else 'V4 missed rate: Pending Evaluation | 0 evaluated runs'),
      p(if (is.null(delta)) 'Improvement and 95% confidence interval: Pending comparable run-level data' else sprintf('Improvement %.1f percentage points (95%% CI %.1f to %.1f)',delta$percentage_points,delta$ci_low,delta$ci_high)))
  })
  output$baseline_caption <- renderText(sprintf('V2 report: %d runs, %d opportunities and %d misses across A-E. V4 plan: %d independent generations in randomized order.',data()$baseline$total_runs,data()$baseline$opportunities,data()$baseline$missed,data()$statistics$planned_v4_runs))
  width_for <- function(id) function() {
    value <- session$clientData[[paste0('output_',id,'_width')]]
    if (is.null(value) || !is.finite(value) || value < 1) 900 else max(80,value)
  }
  responsive_plot <- function(plot,id) {
    width <- width_for(id)()
    # Publication titles live in export figures; the web poster supplies its context.
    plot <- plot + labs(title=NULL,subtitle=NULL,caption=NULL) + research_theme(if(width<600) 8 else 11)
    if(id=='coverage' && !nrow(as_table(data()$runs)))
      plot$layers <- Filter(function(layer) !inherits(layer$geom,'GeomText'),plot$layers)
    if(width<600) {
      plot <- plot + research_theme(9) + theme(legend.position='none',axis.title=element_blank(),
        axis.text=element_text(size=8),plot.margin=margin(4,6,4,6))
      if(id=='pareto') plot <- plot + scale_x_discrete(labels=function(x) vapply(x,function(label) paste(strwrap(label,width=10),collapse='\n'),character(1))) +
        theme(axis.text.x=element_text(size=8,angle=0,hjust=.5))
    }
    plot
  }
  output$coverage <- renderPlot(responsive_plot(coverage_plot(data()),'coverage'),res=96,width=width_for('coverage'),height=function() {h<-session$clientData$output_coverage_height; if(is.null(h)||h<1) 250 else h},
    alt='Academic coverage figure. Historical V2 aggregate and accepted run observations remain separate.')
  output$pareto <- renderPlot(responsive_plot(pareto_plot(data()),'pareto'),res=96,width=width_for('pareto'),height=function() {h<-session$clientData$output_pareto_height; if(is.null(h)||h<1) 250 else h},
    alt='Academic Pareto of missed reference failure modes, using validated category counts.')
  output$pareto_detail <- renderUI({
    selected <- Filter(Negate(is.null),lapply(workspace_filters(input),scope_value))
    if(length(selected)) return(p('Missed-reason totals are available for the published cohort. Clear filters to inspect those totals.'))
    dashboard_pareto(data())
  })
  output$criteria <- renderUI({criteria <- data()$statistics$criteria; div(class='criteria-grid',lapply(names(criteria),function(k) div(strong(criteria[[k]]),span(gsub('_',' ',k)))))})
  output$pending_versions <- renderUI({
    available <- unique(as_table(data()$runs)$skill_version)
    p(paste(paste(setdiff(c('v2.0','v3.0','v3.0-audit','v4.0'),available),'Pending Evaluation'),collapse=' | '))
  })
  filtered <- reactive({
    runs <- as_table(data()$runs)
    if (!nrow(runs)) return(runs)
    keep <- runs$skill_version %in% input$versions & runs$system %in% input$systems
    if (!is.null(input$run) && input$run!='All') keep <- keep & runs$run_id==input$run
    if (!is.null(input$eval_status) && input$eval_status!='All') keep <- keep & runs$evaluation_status==input$eval_status
    if ('generation_timestamp' %in% names(runs)) {
      dates <- as.Date(substr(runs$generation_timestamp,1,10))
      keep <- keep & (is.na(dates) | (dates>=input$dates[1] & dates<=input$dates[2]))
    }
    runs[which(keep),,drop=FALSE]
  })
  output$run_plot <- renderUI(dashboard_runs(data(),filtered()))
  output$selected_chart_run <- renderUI({
    r <- as_table(data()$runs); if(is.null(input$chart_run) || !nrow(r)) return(NULL)
    r <- r[r$run_id==input$chart_run,,drop=FALSE]
    if(!nrow(r)) return(NULL)
    chart_panel('Selected evaluated FMEA',chart_details(r,'Run metadata'))
  })
  output$version_summary <- renderTable(as_table(data()$per_version),digits=2)
  output$system_summary <- renderTable(as_table(data()$per_system),digits=2)
  output$run_table <- renderTable(filtered(),digits=2)
  output$statistics <- renderPrint(data()$statistics)
  output$registry <- renderTable(as_table(data()$registry))
  output$coverage_table <- renderTable({
    x <- as_table(data()$coverage_summary)
    if(!nrow(x)) data.frame(Status='No independently audited component coverage available') else x
  })
  output$extras <- renderTable({x <- as_table(data()$per_version); if(nrow(x)) x[,c('skill_version','mean_extra_rows'),drop=FALSE] else data.frame(Status='Pending evaluated run-level extras')})
  output$review <- renderTable(data.frame(Metric=names(data()$review_summary),Value=unlist(data()$review_summary)))
  output$poster_pdf <- downloadHandler(filename=function() 'sigma-airlines-poster.pdf',content=function(file) poster_export(data(),file))

  output$historical_baseline <- renderTable({
    b <- data()$baseline
    values <- list('Evaluated FMEAs (reported)'=b$total_runs,'Reference opportunities'=b$opportunities,
      'Missed reference modes'=b$missed,'Pooled missed percentage (reported)'=b$pooled_missed_percentage_reported,
      'Pooled coverage percentage (reported)'=b$pooled_coverage_percentage_reported,
      'DPMO from aggregate counts'=b$dpmo_recalculated,'Approximate reported sigma'=b$sigma_reported_approximate,
      'Unmatched generated rows'=b$extra_unmatched_rows,'Approximate extras per run'=b$extra_per_run_reported_approximate)
    quality <- b$conditional_quality_reported
    for(name in names(quality)) values[[paste(gsub('_',' ',name),'reported percent')]] <- 100*quality[[name]]
    if(!is.null(b$judge_repeatability_reported)) {
      values[['Reported judge agreement percent']] <- 100*b$judge_repeatability_reported$agreement
      values[["Reported Fleiss kappa"]] <- b$judge_repeatability_reported$fleiss_kappa
    }
    data.frame(Quantity=names(values),Value=vapply(values,function(x) if(is.null(x)) 'Unavailable' else format(x,digits=6),character(1)))
  })
  # Operational records and judged observations remain separate reactive tables.
  number_text <- function(x,prefix='',digits=0) if(is.null(x) || !length(x) || is.na(x)) 'Unavailable' else paste0(prefix,format(round(x,digits),big.mark=',',trim=TRUE))
  kpi <- function(value,label,detail='') div(class='kpi',strong(value),span(label),tags$small(detail))
  active_plan <- reactive({refresh_key(); read_workspace_plan(plan_path)})
  output$workspace_status <- renderUI({
    sync <- data()$operations$sync
    div(class='workspace-context',span('Round 2 / V4.0',class='experiment-label'),
      span(paste('Last sync:',if(is.null(sync$last_successful_sync)) 'not yet completed' else sync$last_successful_sync)),
      span(if(grepl('retaining',refresh_key()$status)) 'Source: cached snapshot' else 'Source: validated local snapshot'),
      span(if(is.null(sync$status)) 'Offline' else gsub('_',' ',tolower(sync$status))))
  })
  output$experiment_progress <- renderUI(workspace_progress(data(),active_plan()))
  output$historical_reference <- renderUI({b <- data()$baseline; p(paste('Historical V2 report:',b$total_runs,'evaluated FMEAs;',b$pooled_missed_percentage_reported,'% pooled missed. Separate from the current experiment.'))})
  output$mission_kpis <- renderUI({
    ops <- data()$operations; runs <- as_table(data()$runs); versions <- as_table(data()$per_version)
    current <- if(nrow(versions)) versions[versions$skill_version=='v4.0',,drop=FALSE] else versions
    v4 <- if(nrow(runs)) runs[runs$skill_version=='v4.0',,drop=FALSE] else runs
    exact_cohort <- nrow(v4)>0 && all(v4$run_id %in% active_plan()$runs$run_id)
    missed <- if(exact_cohort && nrow(current)) paste0(number_text(current$pooled_missed_percentage[1],digits=1),'%') else 'Pending'
    div(class='kpi-row',
      kpi(number_text(ops$total_generated),'Total generations','Successful receipts / all versions'),
      kpi(number_text(ops$awaiting_judge),'Awaiting evaluation','All registered versions'),
      kpi(number_text(ops$evaluated_fmeas),'Evaluated FMEAs','Selected accepted evaluations / all versions'),
      kpi(missed,'Current missed rate','Round 2 / V4.0 / pooled opportunities'))
  })
  output$sync_summary <- renderText({ops <- data()$operations; if(is.null(ops)) return('Legacy snapshot: registry synchronization pending')
    paste('Last successful synchronization:',if(is.null(ops$sync$last_successful_sync)) 'Not yet synchronized' else ops$sync$last_successful_sync,
      '| Polling status:',ops$sync$status,'| Registered generations:',ops$registered_generations)})
  activity_data <- reactive({
    x <- generations(); folder <- file.path(project_root,'results','dashboard-activity',session$token)
    dir.create(folder,recursive=TRUE,showWarnings=FALSE)
    path <- file.path(folder,'receipts.json'); target <- file.path(folder,'activity.json')
    jsonlite::write_json(x,path,dataframe='rows',auto_unbox=TRUE,null='null',digits=NA)
    python <- Sys.getenv('SIGMA_PYTHON',file.path(project_root,'.venv','gemini','Scripts','python.exe'))
    if(!file.exists(python)) python <- Sys.which('python')
    previous <- getwd(); setwd(project_root); on.exit(setwd(previous),add=TRUE)
    status <- suppressWarnings(system2(python,c('-m','analysis.engineering','operations','--input',shQuote(path),'--output',shQuote(target)),stdout=FALSE,stderr=FALSE))
    if(status!=0) return(NULL)
    list(registry=x,evaluations=list(),operations=jsonlite::fromJSON(target))
  })
  output$mission_activity <- renderUI({d<-activity_data();if(is.null(d)) chart_empty('Activity unavailable','Verify Python setup, then refresh.') else dashboard_activity(d)})
  output$mission_quality <- renderUI(dashboard_versions(data()))
  output$quality_accuracy <- renderUI(dashboard_agreement(data()))
  output$quality_completeness <- renderUI(dashboard_runs(data(),filtered(),scatter=TRUE))
  output$poster_criteria <- renderUI({criteria <- data()$statistics$criteria; div(class='criteria-grid',lapply(names(criteria),function(k) div(strong(criteria[[k]]),span(gsub('_',' ',k)))))})
  output$workflow_table <- renderTable({x <- as_table(data()$workflow_executions); if(!nrow(x)) return(data.frame(Status='No GitHub executions synchronized'))
    tail(x[,intersect(c('workflow_run_id','run_attempt','status','conclusion','created_at'),names(x)),drop=FALSE],5)})
  registry <- reactive({
    rows <- as_table(data()$registry)
    if(!nrow(rows)) return(rows)
    manifest <- active_plan()$runs
    identities <- lapply(seq_len(nrow(rows)),function(i)
      experiment_identity(with_manifest_identity(as.list(rows[i,,drop=FALSE]),manifest),mapping=experiment_mapping))
    rows$resolved_round <- vapply(identities,function(x) if(is.null(x$round)) NA_character_ else x$round,character(1))
    rows$system_display <- vapply(identities,function(x) if(is.null(x$system_name)) 'System unknown' else x$system_name,character(1))
    rows$experiment_label <- vapply(identities,function(x) x$label,character(1))
    evaluations <- as_table(data()$evaluations)
    if(nrow(evaluations)) rows$judge_skill_version <- evaluations$judge_skill_version[match(rows$selected_evaluation,evaluations$evaluation_id)]
    rows
  })
  observe({
    rows <- registry()
    rounds <- sort(unique(c(unname(historical_rounds),rows$resolved_round)),na.last=NA)
    judges <- sort(unique(rows$judge_skill_version),na.last=NA)
    for(pair in list(list('g_round',rounds),list('g_judge',judges))) {
      chosen <- isolate(input[[pair[[1]]]])
      choices <- c('All',pair[[2]])
      updateSelectInput(session,pair[[1]],choices=choices,selected=if(length(chosen)&&chosen %in% choices) chosen else 'All')
    }
  })
  generations <- reactive({
    rows <- filter_generation_rows(registry(),workspace_filters(input))
    if(!nrow(rows)) return(rows)
    status <- scope_value(input$generation_filter)
    if(!is.null(status)) rows <- rows[which(rows$generation_status==status),,drop=FALSE]
    ordering <- if(is.null(input$generation_sort)) 'recent' else input$generation_sort
    key <- switch(ordering,identity=order(rows$system,rows$resolved_round),
      duration=order(rows$generation_seconds,decreasing=TRUE,na.last=TRUE),
      order(rows$generation_timestamp,decreasing=TRUE,na.last=TRUE))
    rows[key,,drop=FALSE]
  })
  output$analytics_duration <- renderUI({
    rows <- generations()
    if(!nrow(rows) || !'generation_seconds' %in% names(rows)) return(p('No timed generations match the current scope.'))
    timed <- rows[which(rows$generation_status=='success' & is.finite(rows$generation_seconds) & rows$generation_seconds>=0),,drop=FALSE]
    if(!nrow(timed)) return(p('No successful generation has a recorded duration in this selection.'))
    labels <- paste(timed$system_display,timed$skill_version,sep=' / ')
    values <- sort(tapply(timed$generation_seconds,labels,median),decreasing=TRUE)
    counts <- table(labels)[names(values)]
    tagList(bar_rows(names(values),as.numeric(values),max(1,values),
      display=paste(vapply(values,generation_duration_label,character(1)),sprintf('(%d runs)',counts))),
      p(class='chart-note','Median recorded generator duration for successful timed runs. Queue and reviewer labor are separate.'))
  })
  generation_table <- function(x,page=1,size=10) {
    if(!nrow(x)) return(chart_empty('No matching generations','Adjust filters or synchronize generation receipts.'))
    columns <- c(run_id='Experiment',skill_version='Skill',generator_model='Model',generation_seconds='Duration',generation_status='Generation',evaluation_status='Judge',generation_timestamp='Timestamp (UTC)')
    labels <- if('experiment_label' %in% names(x)) x$experiment_label else experiment_labels(x,experiment_mapping)
    page <- max(1,min(ceiling(nrow(x)/size),if(is.null(page)) 1 else as.integer(page)))
    indexes <- seq.int((page-1)*size+1,min(page*size,nrow(x)))
    format_cell <- function(k,i) {
      v <- if(k %in% names(x)) x[[k]][i] else NA
      if(is.na(v)) return(if(k=='missed_percentage') 'Pending' else 'Unknown')
      if(k=='run_id') return(labels[i])
      if(k=='generation_seconds') return(generation_duration_label(as.numeric(v)))
      if(k=='missed_percentage') return(paste0(round(as.numeric(v),1),'%'))
      if(k=='generation_timestamp') return(format(as.POSIXct(v,format='%Y-%m-%dT%H:%M:%S',tz='UTC'),'%b %d, %H:%M',tz='UTC'))
      if(k=='generation_status') return(switch(v,success='Generated',failed='Failed',tools::toTitleCase(gsub('_',' ',v))))
      if(k=='evaluation_status') return(switch(v,awaiting_evaluation='Awaiting judge',not_evaluated='Not evaluated',evaluated='Evaluated',tools::toTitleCase(gsub('_',' ',v))))
      v
    }
    html <- tags$table(class='run-table',tags$thead(tags$tr(lapply(unname(columns),tags$th))),tags$tbody(lapply(indexes,function(i) {
      gid <- if('generation_id' %in% names(x)) x$generation_id[i] else x$run_id[i]
      tags$tr(class='clickable-run',tabindex=0,role='button',`data-generation`=gid,
        lapply(names(columns),function(k) tags$td(`data-label`=columns[[k]],title=if(k %in% names(x)) as.character(x[[k]][i]) else '',format_cell(k,i))))
    })))
    tagList(div(class='run-table-wrap',html),p(class='chart-note',paste('Showing',min(indexes),'-',max(indexes),'of',nrow(x),'records. Select a row for full metadata.')))
  }
  output$explorer_table <- renderUI(generation_table(generations(),input$run_page))
  output$recent_activity <- renderUI({x <- as_table(data()$registry); if(nrow(x) && 'generation_timestamp' %in% names(x)) x <- x[order(x$generation_timestamp,decreasing=TRUE,na.last=TRUE),,drop=FALSE]; generation_table(head(x,5))})
  output$generation_detail <- renderUI({
    x <- as_table(data()$registry)
    if(!nrow(x)) return(p('Choose a registered generation to inspect its lifecycle and provenance.'))
    row <- if(!is.null(input$detail_run) && 'generation_id' %in% names(x)) x[x$generation_id==input$detail_run,,drop=FALSE] else head(x,1)
    if(!nrow(row)) return(p('Generation is unavailable in this snapshot.'))
    workflow <- as_table(data()$workflow_executions)
    link <- NULL
    if(nrow(workflow) && 'workflow_execution_id' %in% names(row)) {
      match <- workflow[workflow$execution_id==row$workflow_execution_id[1],,drop=FALSE]
      if(nrow(match) && !is.na(match$url[1])) link <- a('Open GitHub workflow',href=match$url[1],target='_blank',rel='noopener noreferrer')
    }
    if(is.null(link) && 'parent_workflow_run_id' %in% names(row) && !is.na(row$parent_workflow_run_id[1]) && grepl('^[0-9]+$',row$parent_workflow_run_id[1])) link <- a('Open parent workflow (local artifact provenance)',href=paste0('https://github.com/robertwarnold/sigmaairlinesproject/actions/runs/',row$parent_workflow_run_id[1]),target='_blank',rel='noopener noreferrer')
    identity <- experiment_identity(with_manifest_identity(as.list(row),active_plan()$runs),
      if(exists('match',inherits=FALSE)&&nrow(match)) as.list(match[1,,drop=FALSE]) else list(),experiment_mapping)
    engineering_id <- if('engineering_run_id' %in% names(row) && !is.na(row$engineering_run_id[1])) row$engineering_run_id[1] else row$run_id[1]
    div(h3(identity$label),if(length(identity$conflicts)) p(paste('Metadata conflict:',paste(identity$conflicts,collapse=', '))),
      if(!is.null(identity$branch)) p(paste('Branch:',identity$branch)),link,' ',
      workspace_link('explorer','Inspect generated records',`data-open-run`=engineering_id),
      div(class='detail-grid',lapply(names(row),function(k) div(strong(gsub('_',' ',k)),tags$pre(if(is.na(row[[k]][1])) 'Unavailable' else as.character(row[[k]][1]))))))
  })
  output$event_table <- renderTable({x <- as_table(data()$lifecycle_events); if(nrow(x) && !is.null(input$detail_run)) x <- x[x$object_id==input$detail_run,,drop=FALSE]; x})
  set_assumptions <- function(values) {
    for(name in names(values)) {
      if(name=='uncertainty_fraction') updateSliderInput(session,paste0('fin_',name),value=values[[name]])
      else updateNumericInput(session,paste0('fin_',name),value=values[[name]])
    }
  }
  observeEvent(input$reset_finance,{
    updateSelectInput(session,'finance_preset',selected='Baseline')
    set_assumptions(financial_defaults)
  })
  observeEvent(input$finance_preset,{
    values <- financial_defaults
    multiplier <- switch(input$finance_preset,Conservative=1.25,Optimistic=.75,1)
    for(key in c('matched_review_minutes','missed_reconstruction_minutes','extra_review_minutes'))
      values[[key]] <- values[[key]]*multiplier
    set_assumptions(values)
  })
  scenario <- debounce(reactive({
    values <- financial_defaults
    for(name in names(values)) if(!is.null(input[[paste0('fin_',name)]])) values[[name]] <- input[[paste0('fin_',name)]]
    values
  }),700)
  financial_result <- reactive({
    values <- scenario(); snapshot <- data()
    folder <- file.path(project_root,'results','dashboard-scenarios',session$token)
    dir.create(folder,recursive=TRUE,showWarnings=FALSE)
    input_path <- file.path(folder,'assumptions.json'); snapshot_path <- file.path(folder,'snapshot.json'); output_path <- file.path(folder,'scenario.json')
    jsonlite::write_json(values,input_path,auto_unbox=TRUE,digits=NA,null='null')
    jsonlite::write_json(snapshot,snapshot_path,auto_unbox=TRUE,dataframe='rows',digits=NA,null='null')
    python <- Sys.getenv('SIGMA_PYTHON',file.path(project_root,'.venv','gemini','Scripts','python.exe'))
    if(!file.exists(python)) python <- Sys.which('python')
    previous <- getwd(); setwd(project_root); on.exit(setwd(previous),add=TRUE)
    status <- suppressWarnings(system2(python,c('-m','analysis.research','finance','--snapshot',shQuote(snapshot_path),'--assumptions',shQuote(input_path),'--output',shQuote(output_path)),stdout=FALSE,stderr=FALSE))
    if(status!=0 || !file.exists(output_path)) return(list(status='Scenario unavailable: check Python dependencies and nonnegative assumptions.',data=NULL))
    list(status='MODELED NOT MEASURED | Python cost model and 10,000 deterministic simulation draws | Research data unchanged',data=jsonlite::fromJSON(output_path))
  })
  financial <- reactive(financial_result()$data)
  executive_server(input,output,data,historical_metrics,financial,number_text,historical)
  observeEvent(input$open_system,updateSelectInput(session,'g_system',selected=input$open_system))
  observeEvent(input$open_run,updateSelectInput(session,'g_run',selected=input$open_run))
  output$active_analysis_filters <- renderText(scope_text(scope_value(input$g_system),scope_value(input$g_round),
    scope_value(input$g_skill),scope_value(input$g_judge),scope_dates(input$g_dates),
    lapply(list(input$g_run,input$g_subsystem,input$g_model,input$g_review),scope_value),experiment_mapping))
  output$scope_evidence <- renderText({
    metrics <- historical_metrics()$metrics
    if(!length(metrics)) {
      if(is.null(historical()) && is.null(scope_value(input$g_system)) &&
          (is.null(scope_value(input$g_round)) || input$g_round=='1') &&
          (is.null(scope_value(input$g_skill)) || input$g_skill=='v2.0'))
        return(sprintf('Historical evidence: Round 1 | V2.0 | %s reported runs',data()$baseline$total_runs))
      return('Historical cohort unavailable for this system, round and skill selection.')
    }
    rounds <- unique(unname(historical_rounds[names(metrics)]))
    paste0('Historical evidence: ',sum(vapply(metrics,function(x) x$runs,numeric(1))), ' runs',
      ' | Round',if(length(rounds)>1) 's ' else ' ',paste(rounds,collapse='-'),' | ',paste(names(metrics),collapse=' / '),
      ' | system, round and skill filters apply')
  })
  output$financial_status <- renderText(financial_result()$status)
  output$finance_inputs <- renderTable({
    f <- financial(); req(f)
    data.frame(Assumption=gsub('_',' ',names(f$assumptions)),Value=unlist(f$assumptions),row.names=NULL)
  })
  output$finance_provenance <- renderUI({
    f <- financial(); req(f)
    tagList(p(f$basis),p('Manual cost is labor rate times manual hours. Assisted cost combines paid engineering activities and assumed API attempt cost adjusted for success probability. First-year net benefit subtracts implementation and maintenance.'),
      p('Calculation: analysis.research.finance via the financial-impact cost model. Presets vary three review effort rates; the live table reflects edits. API amounts are editable planning inputs.'),
      p('The illustrative $92.71/hour rate scales the May 2025 BLS aerospace engineer median wage by the June 2026 private-industry compensation-to-wage ratio. Source periods and inputs are recorded in analysis/financial_impact/sources.json.'))
  })
  output$finance_export <- downloadHandler(filename=function() 'sigma-financial-scenario.csv',content=function(file) {
    f <- financial(); req(f)
    scalar <- function(values,section) {
      keep <- lengths(values)==1L
      data.frame(section=section,metric=names(values)[keep],value=as.character(unlist(values[keep])),row.names=NULL)
    }
    write.csv(rbind(scalar(f$assumptions,'Assumption'),scalar(f$modeled,'Modeled'),
      data.frame(section='Provenance',metric=c('Basis','Calculation'),value=c(f$basis,'analysis.research.finance / cost_model'))),file,row.names=FALSE)
  })
  output$finance_brief <- downloadHandler(filename=function() 'sigma-financial-decision-brief.txt',content=function(file) {
    f <- financial(); req(f)
    writeLines(c('Sigma Airlines financial decision brief','Modeled planning scenario',
      sprintf('Workload: %s FMEAs per year',f$assumptions$annual_volume),
      sprintf('First-year net benefit: $%.2f',f$modeled$first_year_net_savings),
      sprintf('Manual labor and AI-assisted cost per FMEA: $%.2f and $%.2f',f$modeled$manual_per_fmea,f$modeled$ai_per_fmea),
      f$basis,'Measure paired engineering labor and review burden before approving a budget.','',
      'Scenario inputs',paste(names(f$assumptions),unlist(f$assumptions),sep=': ')),file)
  })
  output$financial_metrics <- renderUI({f <- financial(); if(is.null(f)) return(p('Scenario calculation pending'))
    div(class='finance-outcomes',
      kpi(number_text(f$modeled$first_year_net_savings,'$',0),'Modeled first-year net benefit','After implementation and maintenance'),
      kpi(number_text(f$modeled$percentage_reduction,'',1),'Unit cost reduction (%)','Modeled before fixed costs'),
      kpi(number_text(f$modeled$ai_per_fmea,'$',0),'Modeled assisted cost / FMEA','Labor and expected API costs'),
      kpi(number_text(f$modeled$break_even_fmeas),'Break-even workload','FMEAs / modeled threshold'))
  })
  output$finance_cost <- renderUI({
    f <- financial(); req(f)
    values <- c(f$modeled$manual_per_fmea,f$modeled$ai_per_fmea)
    bar_rows(c('Manual','AI-assisted'),values,max(1,values),display=sprintf('$%.2f',values))
  })
  output$finance_distribution <- renderUI(dashboard_finance(financial(),'simulation'))
  output$finance_breakdown <- renderUI(dashboard_finance(financial(),'breakdown'))
  output$finance_sensitivity <- renderUI(dashboard_finance(financial(),'sensitivity'))
  output$finance_spending <- renderUI(dashboard_finance(financial(),'spending'))
  output$finance_versions <- renderUI(dashboard_finance(financial(),'versions'))
  output$observed_costs <- renderTable({f <- financial(); if(is.null(f)) return(data.frame(Status='Unavailable')); data.frame(Metric=names(f$measured),Value=vapply(f$measured,function(x) if(is.null(x)) 'Unavailable' else as.character(x),character(1)))})
  output$review_costs <- renderTable(as_table(financial()$quality_review_estimates),digits=2)
  output$historical_finance <- renderTable({h <- financial()$historical_scenario; if(is.null(h)) return(data.frame(Status='Pending')); data.frame(Metric=names(h),Value=vapply(h,function(x) paste(x,collapse=' to '),character(1)))})

  engineering_server(input,output,session,research=data,historical=historical,identity_mapping=experiment_mapping,run_registry=registry)
}
shinyApp(ui,server)
