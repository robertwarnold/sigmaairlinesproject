# Sigma Airlines: no API clients or private row data are loaded in this app.
source('bootstrap.R')
source('data.R'); source('plots.R'); source('poster.R'); source('charts.R')
library(shiny); library(bslib)
source_path <- Sys.getenv('SIGMA_DASHBOARD_DATA', file.path(project_root,'results','research','current.json'))
fallback <- 'data/baseline.json'
financial_defaults <- jsonlite::fromJSON('data/financial-defaults.json')
ui <- page_navbar(
  title = 'Sigma Airlines', id = 'view', selected = 'Mission control', fillable=FALSE,
  theme = bs_theme(version=5,bg='#0c1118',fg='#e9f0f6',primary='#6ac9df',base_font='sans-serif'),
  header = tagList(tags$head(chart_css_tokens(),tags$link(rel='stylesheet',type='text/css',href='research.css'),tags$script(src='presentation.js'),tags$script(src='charts.js')),
    div(class='evidence-strip',textOutput('evidence_status'),actionButton('refresh','Refresh data'),
        actionButton('presentation_toggle','Focus presentation'),downloadButton('poster_pdf','Export poster PDF'))),
  nav_panel('Mission control',
    div(class='page-intro',h1('Research mission control'),p('Generation is an operational outcome. Quality requires independent evaluation.')),
    uiOutput('mission_kpis'),
    div(class='chart-grid-layout',chart_panel('Generation activity',uiOutput('mission_activity')),
      chart_panel('Skill version comparison',uiOutput('mission_quality'))),
    div(class='research-panel',h2('Recent activity'),uiOutput('recent_activity')),
    layout_columns(div(class='research-panel',h2('Research target progress'),uiOutput('criteria')),
      div(class='research-panel',h2('Synchronization'),textOutput('sync_summary'),tableOutput('workflow_table')),col_widths=c(6,6))),
  nav_panel('Experiment explorer',
    div(class='page-intro',h1('Every generation. Every evaluation.'),p('Click a generation to inspect safe provenance. Private rows and judge notes remain private.')),
    layout_sidebar(sidebar=sidebar(
      textInput('search','Search run or model'),selectInput('systems','Systems',choices=LETTERS[1:5],selected=LETTERS[1:5],multiple=TRUE),
      selectInput('versions','Skill versions',choices=c('v2.0','v3.0','v3.0-audit','v4.0'),selected=c('v2.0','v3.0','v3.0-audit','v4.0'),multiple=TRUE),
      textInput('batch','Batch contains'),textInput('workflow_filter','Workflow contains'),
      selectInput('generation_filter','Generation status',choices=c('All','planned','queued','running','success','failed')),
      selectInput('eval_status','Evaluation status',choices=c('All','evaluated','awaiting_evaluation','not_evaluated')),
      dateRangeInput('dates','Generation date',start='2026-01-01',end=Sys.Date())),
      uiOutput('explorer_table'),h2('Generation detail'),uiOutput('generation_detail'),
      h2('Lifecycle history'),tableOutput('event_table'))),
  nav_panel('Engineering quality',
    div(class='page-intro',h1('Coverage supported by evidence'),uiOutput('pending_versions')),
    chart_panel('Missed failure modes by run',uiOutput('run_plot'), 'Accepted evaluations only | missed reference opportunities (%) | target below 20%'),
    uiOutput('selected_chart_run'),
    div(class='chart-grid-layout',chart_panel('Miss categories',uiOutput('pareto_detail')),
      chart_panel('Field-level agreement',uiOutput('quality_accuracy'))),
    tags$details(class='analysis-details',tags$summary('Output completeness and supporting research tables'),
      chart_panel('Generated rows and missed percentage',uiOutput('quality_completeness')),
      h2('Version summary'),tableOutput('version_summary'),h2('System summary'),tableOutput('system_summary'),
      h2('Component coverage'),tableOutput('coverage_table'),h2('Unmatched rows (not adjudicated false positives)'),tableOutput('extras')),
    tags$details(class='analysis-details',tags$summary('Inference, acceptance criteria and human review'),
      verbatimTextOutput('statistics'),tableOutput('review'))),
  nav_panel('Financial analysis',
    div(class='page-intro',h1('What does better coverage cost?'),p('Measured spending and modeled savings are distinct. Missing invoices remain unknown.')),
    tags$div(class='financial-workspace',
      tags$details(class='finance-assumptions',tags$summary('Edit scenario assumptions'),div(class='assumption-grid',
      numericInput('fin_annual_volume','Annual FMEAs',50,min=1),numericInput('fin_labor_rate','Loaded rate (USD/hour)',92.71,min=0),
      numericInput('fin_manual_hours','Manual hours/FMEA',financial_defaults$manual_hours,min=0),
      numericInput('fin_setup_hours','AI setup hours',.5,min=0),numericInput('fin_matched_review_minutes','Matched-item review minutes',3,min=0),
      numericInput('fin_missed_reconstruction_minutes','Missed-item reconstruction minutes',20,min=0),
      numericInput('fin_extra_review_minutes','Extra-row review minutes',5,min=0),numericInput('fin_approval_hours','Final approval hours',1,min=0),
      numericInput('fin_development_usd','Implementation cost (USD)',3500,min=0),numericInput('fin_maintenance_usd','Annual maintenance (USD)',0,min=0),
      numericInput('fin_api_usd_per_attempt','Assumed API USD/attempt',1,min=0),numericInput('fin_success_probability','Assumed success probability',.8,min=.01,max=1),
      sliderInput('fin_uncertainty_fraction','Scenario uncertainty +/- fraction',min=0,max=.6,value=.2,step=.05),
      actionButton('reset_finance','Reset to baseline assumptions'))),
      tags$p(class='chart-note',textOutput('financial_status')),uiOutput('financial_metrics'),
      div(class='chart-grid-layout',chart_panel('Annual operating cost',uiOutput('finance_cost'),'Modeled USD | same annual workload'),
        chart_panel('First-year net savings',uiOutput('finance_distribution'),'Modeled scenario, not verified savings')),
      tags$details(class='analysis-details',tags$summary('Cost drivers and sensitivity'),
        div(class='chart-grid-layout',chart_panel('Cost per FMEA',uiOutput('finance_breakdown')),
          chart_panel('Sensitivity to assumptions',uiOutput('finance_sensitivity')))),
      chart_panel('Measured API spending',uiOutput('finance_spending')),
      tags$details(class='analysis-details',tags$summary('Version review costs and billing records'),
        chart_panel('Modeled review cost by version',uiOutput('finance_versions')),
        tableOutput('observed_costs'),tableOutput('review_costs')),
      tags$details(class='analysis-details',tags$summary('Preserved historical planning scenario'),tableOutput('historical_finance')))),
  nav_panel('Research methodology',h1('Research method'),h2('Historical Round 1 report aggregates'),p('Report-derived values only. They are separate from the normalized generation registry and have no reconstructed item records or confidence intervals.'),tableOutput('historical_baseline'),
    h2('Define / Measure / Analyze'),p('Quantity of interest: missed failure-mode opportunities per evaluated run, with separate pooled counts. The V2 report establishes a pooled historical baseline; it cannot reconstruct independent run observations.'),
    h2('Improve'),p('Remote V3 introduced prompt-based unit and failure-type checks. The complementary local V3 audit emitted structured links. V4 adds an independent input inventory, deterministic gap audit and targeted remediation preparation.'),
    h2('Control'),p('Freeze model settings, package hashes, judge v1.2 and human reference revisions. Validate every receipt and judge import. Preserve original AI decisions alongside engineer review and adjudication.'),
    h2('Inference and limitations'),p('Primary: V2 versus V4. Additive model: missed_percentage ~ skill_version + system. Independent-run bootstrap within version/system retains equal system weights. At least two runs per cell are needed for intervals; four planned runs per cell still yield limited precision.'),
    p('Sigma is inverse-normal yield plus the conventional 1.5 shift, not a certification. Bounded percentages, variance, independence and additive-model assumptions need review. Canonical package 0.3 is a different workflow and is excluded.'),
    h2('Validation / approval'),p('Schema validity, model completeness claims and engineering acceptance are distinct. No live evaluations are fabricated. Public hosting and sanitized-data publication require explicit approval.')),
  nav_panel('Presentation mode',
    div(class = 'poster',
      div(class = 'poster-title',p(class = 'presentation-context','SYSEN 5300 / Six Sigma Research'),
          h1('Can structured engineering coverage reduce missed failure modes?'),
          p('A controlled comparison of AI-generated FMEAs across five engineering systems.')),
      div(class = 'poster-evidence',uiOutput('poster_results')),
      layout_columns(plotOutput('coverage',height = '300px'),plotOutput('pareto',height = '300px'),col_widths = c(6,6)),
      div(class = 'poster-narrative',
          tags$section(h2('Data'),textOutput('baseline_caption'),p('Report aggregates and validated run-level observations remain separate.')),
          tags$section(h2('Method'),p('DMAIC Improve / Control. Independent input inventory, deterministic structural audit, unchanged external AI judge, sampled engineering review.'),p('Python computes additive ANOVA and system-stratified bootstrap 95% intervals.')),
          tags$section(h2('Discussion / implications'),p('Higher output volume is not proof of engineering quality. Track extra rows, correctness and provisional ratings alongside coverage.'),p('No improvement claim until comparable evaluated observations support it.'))),
      h2('V4 success criteria'),uiOutput('poster_criteria'),
      p(class = 'caption','AI-assisted presentation draft. Students must verify findings, interpret evidence and write their own submitted prose.'))),
  footer=div(class='footer',textOutput('snapshot_status'))
)

server <- function(input,output,session) {
  loader <- make_loader(source_path,fallback)
  # Poll every 30 seconds and on manual refresh. Loader retains validated cache.
  refresh_key <- reactivePoll(30000,session,
    checkFunc = function() paste(input$refresh, if (file.exists(source_path)) file.info(source_path)$mtime else floor(as.numeric(Sys.time())/30)),
    valueFunc = function() loader())
  data <- reactive(refresh_key()$data)
  output$evidence_status <- renderText(paste('Evidence:',data()$research_status,'|',refresh_key()$status))
  output$snapshot_status <- renderText(paste('Last updated',data()$last_updated,'| Snapshot',substr(data()$data_version,1,12),'|',data()$validation_status))
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
    if(width<600) plot <- plot + theme(legend.position='none',axis.title=element_blank(),
      axis.text.x=element_text(size=6),plot.margin=margin(6,8,6,8))
    plot
  }
  output$coverage <- renderPlot(responsive_plot(coverage_plot(data()),'coverage'),res=96,width=width_for('coverage'),height=300,
    alt='Academic coverage figure. Historical V2 aggregate and accepted run observations remain separate.')
  output$pareto <- renderPlot(responsive_plot(pareto_plot(data()),'pareto'),res=96,width=width_for('pareto'),height=300,
    alt='Academic Pareto of missed reference failure modes, using validated category counts.')
  output$pareto_detail <- renderUI(dashboard_pareto(data()))
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
  current_quality <- reactive({
    versions <- as_table(data()$per_version)
    if(nrow(versions)) {
      order <- match(versions$skill_version,c('v2.0','v3.0','v3.0-audit','v4.0'))
      row <- versions[which.max(order),,drop=FALSE]
      return(list(missed=row$pooled_missed_percentage,sigma=row$sigma_1_5_shift,basis=paste(row$skill_version,'selected evaluations; pooled opportunities')))
    }
    list(missed=data()$baseline$pooled_missed_percentage_reported,sigma=data()$baseline$sigma_reported_approximate,basis='V2 historical report aggregate; not current V4 performance')
  })
  output$mission_kpis <- renderUI({
    ops <- data()$operations; q <- current_quality(); finance <- data()$financial
    div(class='kpi-row',
      kpi(number_text(ops$total_generated),'FMEAs generated','Successful generation receipts'),
      kpi(number_text(ops$evaluated_fmeas),'Evaluated FMEAs','One selected evaluation per FMEA'),
      kpi(number_text(ops$awaiting_judge),'Awaiting judge','Successful, independently unevaluated'),
      kpi(paste0(number_text(q$missed,digits=1),'%'),'Pooled missed percentage',q$basis),
      kpi(number_text(q$sigma,digits=2),'Sigma level','Conventional +1.5 shift; report value approximate'),
      kpi(number_text(finance$measured$estimated_api_spending,'$',2),'Estimated research API cost','Missing pricing remains unknown'))
  })
  output$sync_summary <- renderText({ops <- data()$operations; if(is.null(ops)) return('Legacy snapshot: registry synchronization pending')
    paste('Last successful synchronization:',if(is.null(ops$sync$last_successful_sync)) 'Not yet synchronized' else ops$sync$last_successful_sync,
      '| Polling status:',ops$sync$status,'| Registered generations:',ops$registered_generations)})
  output$mission_activity <- renderUI(dashboard_activity(data()))
  output$mission_quality <- renderUI(dashboard_versions(data()))
  output$quality_accuracy <- renderUI(dashboard_agreement(data()))
  output$quality_completeness <- renderUI(dashboard_runs(data(),filtered(),scatter=TRUE))
  output$poster_criteria <- renderUI({criteria <- data()$statistics$criteria; div(class='criteria-grid',lapply(names(criteria),function(k) div(strong(criteria[[k]]),span(gsub('_',' ',k)))))})
  output$workflow_table <- renderTable({x <- as_table(data()$workflow_executions); if(!nrow(x)) return(data.frame(Status='No GitHub executions synchronized'))
    tail(x[,intersect(c('workflow_run_id','run_attempt','status','conclusion','created_at'),names(x)),drop=FALSE],5)})
  generations <- reactive({
    x <- as_table(data()$registry)
    if(!nrow(x)) return(x)
    keep <- rep(TRUE,nrow(x))
    if(!is.null(input$systems)) keep <- keep & x$system %in% input$systems
    if(!is.null(input$versions)) keep <- keep & x$skill_version %in% input$versions
    if(!is.null(input$search) && nzchar(input$search)) keep <- keep & (grepl(input$search,x$run_id,fixed=TRUE) | grepl(input$search,x$generator_model,fixed=TRUE))
    if(!is.null(input$batch) && nzchar(input$batch) && 'batch' %in% names(x)) keep <- keep & grepl(input$batch,x$batch,fixed=TRUE)
    if(!is.null(input$workflow_filter) && nzchar(input$workflow_filter) && 'workflow_execution_id' %in% names(x)) keep <- keep & grepl(input$workflow_filter,x$workflow_execution_id,fixed=TRUE)
    if(!is.null(input$generation_filter) && input$generation_filter!='All') keep <- keep & x$generation_status==input$generation_filter
    if(!is.null(input$eval_status) && input$eval_status!='All') keep <- keep & x$evaluation_status==input$eval_status
    if('generation_timestamp' %in% names(x) && !is.null(input$dates)) {
      dates <- as.Date(substr(x$generation_timestamp,1,10)); keep <- keep & (is.na(dates) | (dates>=input$dates[1] & dates<=input$dates[2]))
    }
    x[which(keep),,drop=FALSE]
  })
  generation_table <- function(x) {
    if(!nrow(x)) return(p('No registered generations match this view. Synchronize receipts; no FMEAs are inferred from workflow success.'))
    columns <- intersect(c('system','skill_version','run_id','parent_workflow_run_id','replicate','generated_rows','generation_seconds','state','evaluation_label','missed_percentage','generation_timestamp'),names(x))
    table <- tags$table(class='table',tags$thead(tags$tr(lapply(columns,tags$th))),
      tags$tbody(lapply(seq_len(min(200,nrow(x))),function(i) {
        gid <- if('generation_id' %in% names(x)) x$generation_id[i] else x$run_id[i]
        tags$tr(class='clickable-run',tabindex=0,onclick=paste0("Shiny.setInputValue('detail_run',",jsonlite::toJSON(gid,auto_unbox=TRUE),",{priority:'event'})"),
          lapply(columns,function(k) tags$td(title=as.character(x[[k]][i]),if(is.na(x[[k]][i])) 'Unavailable' else as.character(x[[k]][i]))))
      })))
    div(class='table-responsive',table)
  }
  output$explorer_table <- renderUI(generation_table(generations()))
  output$recent_activity <- renderUI({x <- as_table(data()$registry); if(nrow(x) && 'generation_timestamp' %in% names(x)) x <- x[order(x$generation_timestamp,decreasing=TRUE,na.last=TRUE),,drop=FALSE]; generation_table(head(x,6))})
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
    div(link,div(class='detail-grid',lapply(names(row),function(k) div(strong(gsub('_',' ',k)),tags$pre(if(is.na(row[[k]][1])) 'Unavailable' else as.character(row[[k]][1]))))))
  })
  output$event_table <- renderTable({x <- as_table(data()$lifecycle_events); if(nrow(x) && !is.null(input$detail_run)) x <- x[x$object_id==input$detail_run,,drop=FALSE]; x})
  observeEvent(input$reset_finance,{
    for(name in names(financial_defaults)) {
      if(name=='uncertainty_fraction') updateSliderInput(session,paste0('fin_',name),value=financial_defaults[[name]])
      else updateNumericInput(session,paste0('fin_',name),value=financial_defaults[[name]])
    }
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
  output$financial_status <- renderText(financial_result()$status)
  output$financial_metrics <- renderUI({f <- financial(); if(is.null(f)) return(p('Scenario calculation pending'))
    div(class='finance-outcomes',
      kpi(number_text(f$modeled$first_year_net_savings,'$',0),'Modeled first-year savings','Includes implementation and maintenance'),
      kpi(number_text(f$modeled$break_even_fmeas),'Break-even FMEAs','Unknown if unit savings are nonpositive'),
      kpi(number_text(f$modeled$review_cost_per_fmea,'$',0),'Modeled review / FMEA',f$basis))
  })
  output$finance_cost <- renderUI(dashboard_finance(financial(),'comparison'))
  output$finance_distribution <- renderUI(dashboard_finance(financial(),'simulation'))
  output$finance_breakdown <- renderUI(dashboard_finance(financial(),'breakdown'))
  output$finance_sensitivity <- renderUI(dashboard_finance(financial(),'sensitivity'))
  output$finance_spending <- renderUI(dashboard_finance(financial(),'spending'))
  output$finance_versions <- renderUI(dashboard_finance(financial(),'versions'))
  output$observed_costs <- renderTable({f <- financial(); if(is.null(f)) return(data.frame(Status='Unavailable')); data.frame(Metric=names(f$measured),Value=vapply(f$measured,function(x) if(is.null(x)) 'Unavailable' else as.character(x),character(1)))})
  output$review_costs <- renderTable(as_table(financial()$quality_review_estimates),digits=2)
  output$historical_finance <- renderTable({h <- financial()$historical_scenario; if(is.null(h)) return(data.frame(Status='Pending')); data.frame(Metric=names(h),Value=vapply(h,function(x) paste(x,collapse=' to '),character(1)))})

}
shinyApp(ui,server)
