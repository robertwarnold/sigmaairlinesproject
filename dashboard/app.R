# Aggregate mode has no private rows. Engineering mode is explicitly loopback-only.
source('bootstrap.R')
source('data.R'); source('plots.R'); source('poster.R'); source('charts.R'); source('workspace.R'); source('engineering.R')
library(shiny); library(bslib)
source_path <- Sys.getenv('SIGMA_DASHBOARD_DATA', file.path(project_root,'results','research','current.json'))
fallback <- 'data/baseline.json'
plan_path <- Sys.getenv('SIGMA_DASHBOARD_MANIFEST',file.path(project_root,'results','v4','round2-plan','experiment_manifest.json'))
financial_defaults <- jsonlite::fromJSON('data/financial-defaults.json')
ui <- page_navbar(
  title = div(class='brand',strong('SIGMA AIRLINES'),span('FMEA RESEARCH PLATFORM')), id = 'view', selected = 'Mission control', fillable=FALSE,
  theme = bs_theme(version=5,bg=chart_tokens$background,fg=chart_tokens$ink,primary=chart_tokens$accent,base_font='sans-serif'),
  header = tagList(tags$head(chart_css_tokens(),tags$link(rel='stylesheet',type='text/css',href='research.css'),tags$script(src='presentation.js'),tags$script(src='charts.js')),
    div(class='evidence-strip',uiOutput('workspace_status'),actionButton('refresh','Refresh data'))),
  nav_panel('Mission Control',value='Mission control',
    div(class='page-intro',h1('Research overview'),p('Generation is progress. Independent evaluation establishes quality.')),
    uiOutput('mission_kpis'),
    div(class='mission-layout',chart_panel('Generation & evaluation activity',uiOutput('mission_activity')),
      chart_panel('Round 2 progress',uiOutput('experiment_progress'))),
    chart_panel('Recent runs',uiOutput('recent_activity')),
    tags$details(class='analysis-details',tags$summary('Historical baseline, acceptance criteria and synchronization'),
      uiOutput('historical_reference'),uiOutput('criteria'),textOutput('sync_summary'),tableOutput('workflow_table'))),
  nav_panel('Experiment Explorer',value='Experiment explorer',
    div(class='page-intro',h1('Experiment explorer'),p('Find a run. Inspect its generation, evaluation and provenance.')),
    tabsetPanel(id='explorer_mode',
      tabPanel('Run registry',value='registry',
    tags$div(tags$details(class='filter-panel',tags$summary('Filter runs'),div(class='filter-grid',
      textInput('search','Search run or model'),selectInput('systems','Systems',choices=LETTERS[1:5],selected=LETTERS[1:5],multiple=TRUE),
      selectInput('versions','Skill versions',choices=c('v2.0','v3.0','v3.0-audit','v4.0'),selected=c('v2.0','v3.0','v3.0-audit','v4.0'),multiple=TRUE),
      textInput('batch','Batch contains'),textInput('workflow_filter','Workflow contains'),
      selectInput('generation_filter','Generation status',choices=c('All','planned','queued','running','success','failed')),
      selectInput('eval_status','Evaluation status',choices=c('All','evaluated','awaiting_evaluation','not_evaluated')),
      dateRangeInput('dates','Generation date',start='2026-01-01',end=Sys.Date()))),
      uiOutput('explorer_table'),numericInput('run_page','Page',1,min=1,width='6rem'),
      tags$details(id='run-detail',class='analysis-details',tags$summary('Selected run details'),uiOutput('generation_detail'),
      tags$details(tags$summary('Lifecycle history'),tableOutput('event_table'))))),
      tabPanel('FMEA workspace',value='workspace',engineering_ui()))),
  nav_panel('Engineering Quality',value='Engineering quality',
    div(class='page-intro',h1('Engineering quality'),p('Accepted evaluations only. Historical aggregates remain a separate reference.')),
    chart_panel('Missed failure modes by run',uiOutput('run_plot'), 'Accepted evaluations only | missed reference opportunities (%) | target below 20%'),
    uiOutput('selected_chart_run'),
    chart_panel('Skill version comparison',uiOutput('mission_quality')),
    tags$details(class='analysis-details',tags$summary('Failure categories and field-level agreement'),
      div(class='chart-grid-layout',chart_panel('Miss categories',uiOutput('pareto_detail')),chart_panel('Field-level agreement',uiOutput('quality_accuracy')))),
    tags$details(class='analysis-details',tags$summary('Output completeness and supporting research tables'),
      chart_panel('Generated rows and missed percentage',uiOutput('quality_completeness')),
      h2('Version summary'),tableOutput('version_summary'),h2('System summary'),tableOutput('system_summary'),
      h2('Component coverage'),tableOutput('coverage_table'),h2('Unmatched rows (not adjudicated false positives)'),tableOutput('extras')),
    tags$details(class='analysis-details',tags$summary('Private engineering risk and experiment comparison'),uiOutput('engineering_risk')),
    tags$details(class='analysis-details',tags$summary('Inference, acceptance criteria and human review'),
      verbatimTextOutput('statistics'),tableOutput('review'))),
  nav_panel('Financial Analysis',value='Financial analysis',
    div(class='page-intro',h1('Financial impact'),p('Modeled economics, measured expenses. Missing invoices remain unknown.')),
    tags$div(class='financial-workspace',
      uiOutput('financial_metrics'),
      tabsetPanel(id='finance_view',type='tabs',
        tabPanel('Cost comparison',value='cost',chart_panel('Annual operating cost',uiOutput('finance_cost'),'Modeled USD at the same annual workload'),
          tags$details(class='analysis-details',tags$summary('Cost breakdown and measured spending'),
            chart_panel('Cost per FMEA',uiOutput('finance_breakdown')),chart_panel('Measured API spending',uiOutput('finance_spending')))),
        tabPanel('Monte Carlo',value='simulation',chart_panel('First-year net savings',uiOutput('finance_distribution'),'Modeled scenario, not verified savings')),
        tabPanel('Sensitivity',value='sensitivity',chart_panel('Sensitivity to assumptions',uiOutput('finance_sensitivity'))),
        tabPanel('Assumptions',value='assumptions',tags$details(open=TRUE,class='finance-assumptions',tags$summary('Scenario assumptions'),div(class='assumption-grid',
      numericInput('fin_annual_volume','Annual FMEAs',50,min=1),numericInput('fin_labor_rate','Loaded rate (USD/hour)',92.71,min=0),
      numericInput('fin_manual_hours','Manual hours/FMEA',financial_defaults$manual_hours,min=0),
      numericInput('fin_setup_hours','AI setup hours',.5,min=0),numericInput('fin_matched_review_minutes','Matched-item review minutes',3,min=0),
      numericInput('fin_missed_reconstruction_minutes','Missed-item reconstruction minutes',20,min=0),
      numericInput('fin_extra_review_minutes','Extra-row review minutes',5,min=0),numericInput('fin_approval_hours','Final approval hours',1,min=0),
      numericInput('fin_development_usd','Implementation cost (USD)',3500,min=0),numericInput('fin_maintenance_usd','Annual maintenance (USD)',0,min=0),
      numericInput('fin_api_usd_per_attempt','Assumed API USD/attempt',1,min=0),numericInput('fin_success_probability','Assumed success probability',.8,min=.01,max=1),
      sliderInput('fin_uncertainty_fraction','Scenario uncertainty +/- fraction',min=0,max=.6,value=.2,step=.05),
      actionButton('reset_finance','Reset Assumptions'))))
),
      tags$details(class='analysis-details',tags$summary('Model provenance and billing records'),textOutput('financial_status'),
        chart_panel('Modeled review cost by version',uiOutput('finance_versions')),tableOutput('observed_costs'),tableOutput('review_costs')),
      tags$details(class='analysis-details',tags$summary('Preserved historical planning scenario'),tableOutput('historical_finance')))),
  nav_panel('Research Methods',value='Research methodology',
    div(class='page-intro',h1('Research methods'),p('A controlled comparison of engineering coverage across five systems.')),
    div(class='method-layout',
      method_section('Research question','Does structured engineering coverage reduce missed failure modes without unsupported output inflation?'),
      method_section('Data sources','Validated generation receipts, independent evaluations and a separate historical V2 report.',
        tagList(p('The reported 18-run baseline is aggregate only. It cannot reconstruct independent run observations or confidence intervals.'),tableOutput('historical_baseline'))),
      method_section('Experimental design','Round 2 plans four independent V4 generations per system, A through E.',
        p('Randomized order; freeze model settings, skill hashes, judge v1.2 and engineer-written reference revisions. Confirm historical settings before live execution.')),
      method_section('Generator and judge','Generation and independent evaluation are separate research events.',
        p('An output passing schema validation has not received engineering approval. Preserve original AI decisions alongside human review and adjudication.')),
      method_section('Metrics','Missed reference opportunities measure coverage; unmatched rows are a guard metric.',
        p('Use reference opportunities for missed percentage and matched reference items for conditional field agreement. Keep pooled rates separate from run-level means.')),
      method_section('Statistical analysis','Additive ANOVA and system-stratified bootstrap intervals, when supported.',
        p('Primary: V2 versus V4. missed_percentage ~ skill_version + system. Preserve equal-system weights. At least two independent runs per cell are required for intervals; four planned runs still limit precision.')),
      method_section('Limitations','No V4 improvement claim before comparable accepted evaluations.',
        p('Report-derived aggregates cannot support run-level inference. Sigma uses inverse-normal yield plus the conventional 1.5 shift. Ratings require engineering review. Canonical package 0.3 remains a separate workflow.')))),
  nav_panel('Presentation Mode',value='Presentation mode',
    div(class='presentation-actions',actionButton('presentation_toggle','Present fullscreen'),downloadButton('poster_pdf','Export poster PDF'),tags$details(tags$summary('Presenter notes'),p('Research question: does structured coverage reduce misses? Describe the independent judge and five-system design. Report the historical baseline separately. V4 results and improvement intervals remain pending until evaluated.'))),
    div(class = 'poster',
      div(class = 'poster-title',
          h1('Can structured engineering coverage reduce missed failure modes?'),
          p('A controlled comparison of AI-generated FMEAs across five engineering systems.')),
      div(class = 'poster-evidence',tags$h2('Results'),uiOutput('poster_results')),
      layout_columns(plotOutput('coverage',height = '300px'),plotOutput('pareto',height = '300px'),col_widths = c(6,6)),
      div(class = 'poster-narrative',
          tags$section(h2('Data'),textOutput('baseline_caption'),p('Report aggregates and validated run-level observations remain separate.')),
          tags$section(h2('Method'),p('DMAIC Improve / Control. Independent input inventory, deterministic structural audit, unchanged external AI judge, sampled engineering review.'),p('Python computes additive ANOVA and system-stratified bootstrap 95% intervals.')),
          tags$section(h2('Discussion'),p('Higher output volume is not proof of engineering quality. Track extra rows, correctness and provisional ratings alongside coverage.'),p('No improvement claim until comparable evaluated observations support it.'))),
      tags$details(class='poster-checks',tags$summary('V4 acceptance criteria'),uiOutput('poster_criteria')),
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
  generation_table <- function(x,page=1,size=10) {
    if(!nrow(x)) return(chart_empty('No matching generations','Adjust filters or synchronize generation receipts.'))
    columns <- c(run_id='Run ID',system='System',skill_version='Skill',generation_status='Generation',evaluation_status='Judge',missed_percentage='Missed',generation_timestamp='Timestamp (UTC)')
    page <- max(1,min(ceiling(nrow(x)/size),if(is.null(page)) 1 else as.integer(page)))
    indexes <- seq.int((page-1)*size+1,min(page*size,nrow(x)))
    format_cell <- function(k,i) {
      v <- if(k %in% names(x)) x[[k]][i] else NA
      if(is.na(v)) return(if(k=='missed_percentage') 'Pending' else 'Unknown')
      if(k=='run_id') { v <- sub('^.*:','',v); return(if(nchar(v)>32) paste0(substr(v,1,29),'...') else v) }
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
      kpi(number_text(f$modeled$annual_operating_savings,'$',0),'Modeled annual savings','Before implementation cost'),
      kpi(if(is.null(f$measured$actual_api_spending)) 'Unknown' else number_text(f$measured$actual_api_spending,'$',2),'Actual API spending','Unknown until invoices are complete'),
      kpi(number_text(f$modeled$review_cost_per_fmea,'$',0),'Estimated review / FMEA','Modeled engineering labor'),
      kpi(number_text(f$modeled$break_even_fmeas),'Break-even workload','FMEAs / modeled threshold'))
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

  engineering_server(input,output,session)
}
shinyApp(ui,server)
