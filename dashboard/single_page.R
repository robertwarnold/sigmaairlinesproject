# A single continuous application surface. Academic export constructors stay separate.
chart_tokens <- list(background='#f7f8fa',surface='#ffffff',raised='#eef2f5',ink='#33414c',
  muted='#65737e',accent='#387fb5',grid='#e0e5e9',warning='#9c6525',failure='#c85360')
palette <- c('v2.0'='#697b8a','v3.0'='#8d78b4','v3.0-audit'='#af782c','v4.0'='#387fb5')
analytics_card <- function(title,id,note=NULL) chart_panel(title,uiOutput(id),note)
analytics_ui <- function(defaults) {
  page_fluid(theme=bs_theme(version=5,bg=chart_tokens$background,fg=chart_tokens$ink,primary=chart_tokens$accent,base_font='sans-serif'),
    tags$head(tags$title('Sigma Airlines | FMEA Engineering Dashboard'),chart_css_tokens(),tags$link(rel='stylesheet',href='research.css'),tags$link(rel='stylesheet',href='single-page.css'),
      tags$script(src='presentation.js'),tags$script(src='charts.js'),tags$script(src='single-page.js')),
    tags$main(class='analytics-page',
      tags$header(class='analytics-header',div(h1('Sigma Airlines \u2014 FMEA Engineering Dashboard'),p('AI-Assisted Failure Mode and Effects Analysis')),
        div(uiOutput('judge_import_action',inline=TRUE),actionButton('refresh','Refresh'),actionButton('generation_help','Generate FMEA'))),
      div(class='global-filters',selectInput('g_run','Experiment / run',choices='All'),selectInput('g_system','System',choices='All'),
        selectInput('g_subsystem','Subsystem',choices='All'),selectInput('g_model','Model / provider',choices='All'),
        selectInput('g_skill','Skill version',choices='All'),dateRangeInput('g_dates','Generation date',start='2020-01-01',end=Sys.Date()),
        selectInput('g_review','Engineering review',choices=c('All','NEEDS_REVIEW','APPROVED','REJECTED')),actionButton('global_reset','Reset filters')),
      div(class='dataset-line',uiOutput('analytics_context'),textOutput('snapshot_status')),
      tags$section(id='health',h2('1 \u00b7 FMEA health at a glance'),uiOutput('analytics_health'),
        div(class='attention-card',h3('What needs attention'),uiOutput('analytics_attention'))),
      tags$section(id='risk-analysis',h2('2 \u00b7 Failure modes and risk distribution'),
        div(class='analytics-grid',analytics_card('Failure modes by subsystem','analytics_subsystems'),analytics_card('Severity versus occurrence','analytics_matrix'),
          analytics_card('RPN distribution','analytics_rpn'),analytics_card('Failure causes by category','analytics_causes'),
          chart_panel('Highest-priority failure modes',tagList(selectInput('priority_order','Order',choices=c('Severity first'='severity','RPN first'='RPN'),width='150px'),uiOutput('analytics_priority'))),
          analytics_card('Corrective action status','analytics_actions'))),
      tags$section(id='ai-performance',h2('3 \u00b7 AI performance and validation'),
        div(class='analytics-grid',analytics_card('Skill version performance','analytics_versions','Structural validation and engineering decisions; not reference recall.'),
          analytics_card('Evidence quality','analytics_evidence'),analytics_card('Generation duration','analytics_duration'),
          analytics_card('Scoring agreement','analytics_agreement','Explicit human rating corrections only / within \u00b11 / at least two pairs per rating.')),
        div(class='analytics-grid three',analytics_card('Duplicate and validation rates by run','analytics_trends'),
          analytics_card('Generation and evaluation activity','mission_activity','Sanitized GitHub generation registry / operational receipts only.'),analytics_card('Independent evaluation','analytics_judge')),
        chart_panel('Experiment summary',uiOutput('analytics_experiments')),
        chart_panel('Historical V2.0 and V3.0 comparison',tableOutput('historical_comparison'),
          'Descriptive results from the archived run-level CSV. Equal-system means give each system the same weight.'),
        tags$details(class='support-details',tags$summary('GitHub run registry, provenance and lifecycle'),
          uiOutput('explorer_table'),numericInput('run_page','Page',1,min=1,width='6rem'),
          tags$details(id='run-detail',tags$summary('Selected generation'),uiOutput('generation_detail'),tableOutput('event_table')),
          uiOutput('experiment_progress'),textOutput('sync_summary'),tableOutput('workflow_table'))),
      tags$details(class='support-details',tags$summary('Financial impact \u00b7 modeled scenarios and measured expenses'),
        uiOutput('financial_metrics'),div(class='analytics-grid',analytics_card('Modeled annual operating cost','finance_cost'),analytics_card('Modeled savings distribution','finance_distribution')),
        tags$details(tags$summary('Assumptions and sensitivity'),div(class='assumption-grid',lapply(names(defaults),function(k) {
          if(k=='uncertainty_fraction') sliderInput(paste0('fin_',k),gsub('_',' ',k),min=0,max=.6,value=defaults[[k]],step=.05)
          else numericInput(paste0('fin_',k),gsub('_',' ',k),defaults[[k]],min=if(k=='success_probability') .01 else if(k=='annual_volume') 1 else 0,
            max=if(k=='success_probability') 1 else NA)
        })),actionButton('reset_finance','Reset assumptions'),uiOutput('finance_sensitivity')),
        div(class='analytics-grid',analytics_card('Modeled cost breakdown','finance_breakdown'),analytics_card('Measured API spending','finance_spending')),
        textOutput('financial_status'),tags$details(tags$summary('Historical scenario and model provenance'),tableOutput('historical_finance'),tableOutput('observed_costs'))),
      tags$section(id='fmea-register',h2('4 \u00b7 Detailed FMEA register'),engineering_ui()),
      tags$details(class='support-details',tags$summary('Research methods, historical baseline and academic exports'),
        p('Generator output, structural validation, source-supported evidence, human review and independent reference evaluation are separate evidence layers.'),
        p('Ratings use the existing integer 1\u201310 policy. S \u2265 9 is a visibility threshold, not a formal risk acceptance criterion. Dashboard V4.1/V4.2 revisions do not imply new FMEA skill versions.'),
        p('Global filters select imported engineering rows and applicable operational records. The frozen historical report, full-cohort inference, financial scenario and academic poster remain separately labeled study-level context.'),
        uiOutput('historical_reference'),tableOutput('historical_baseline'),verbatimTextOutput('statistics'),uiOutput('criteria'),
        div(class='presentation-actions',actionButton('presentation_toggle','Present fullscreen'),downloadButton('poster_pdf','Export poster PDF')),
        div(class='poster',div(class='poster-title',h2('Can structured engineering coverage reduce missed failure modes?')),
          uiOutput('poster_results'),div(class='analytics-grid',plotOutput('coverage',height='270px'),plotOutput('pareto',height='270px')),
          div(class='poster-narrative',tags$section(h3('Data'),textOutput('baseline_caption')),tags$section(h3('Method'),p('DMAIC / independent evaluation / additive ANOVA and system-stratified bootstrap when supported.')),
            tags$section(h3('Discussion'),p('No improvement claim until comparable evaluated observations support it. Higher output volume is not proof of quality.')))),
        tags$details(tags$summary('Presenter notes'),p('Explain the question and five-system design, separate the V2 report from observed runs, distinguish structural checks from engineering approval, and report V4 evaluation as pending when applicable.'))),
      tags$footer('Private source records never enter the public research snapshot. Model calls require separate authorization.')))
}

# Pure projection shared by operational tables; research calculations remain Python-owned.
filter_generation_rows <- function(rows,filters) {
  if(!nrow(rows)) return(rows)
  keep <- rep(TRUE,nrow(rows))
  for(pair in list(c('run','run_id'),c('system','system'),c('model','generator_model'),c('skill','skill_version'))) {
    value <- filters[[pair[1]]]
    if(!is.null(value)&&value!='All') keep <- keep & if(pair[2] %in% names(rows)) !is.na(rows[[pair[2]]]) & rows[[pair[2]]]==value else FALSE
  }
  if(!is.null(filters$dates)&&'generation_timestamp' %in% names(rows)) {
    dates <- as.Date(substr(rows$generation_timestamp,1,10)); keep <- keep & !is.na(dates) & dates>=filters$dates[1] & dates<=filters$dates[2]
  }
  # Generation-level records cannot assert subsystem or row-level review status.
  if((!is.null(filters$subsystem)&&filters$subsystem!='All')||(!is.null(filters$review)&&filters$review!='All')) keep[] <- FALSE
  rows[which(keep),,drop=FALSE]
}

filter_engineering_rows <- function(rows,filters,search='',focus=NULL) {
  if(!nrow(rows)) return(rows)
  keep<-rep(TRUE,nrow(rows))
  fields<-c(run='run_id',system='system',subsystem='subsystem',model='generator_model',skill='skill_version',review='review_status',severity='severity',occurrence='occurrence')
  for(key in names(fields)) {
    value<-filters[[key]]
    if(!is.null(value)&&value!='All') keep<-keep & !is.na(rows[[fields[[key]]]]) & as.character(rows[[fields[[key]]]])==value
  }
  if(!is.null(filters$dates)) {
    dates<-as.Date(substr(rows$generation_timestamp,1,10));keep<-keep & !is.na(dates) & dates>=filters$dates[1] & dates<=filters$dates[2]
  }
  if(!is.null(focus)) keep<-keep & rows$record_id %in% focus
  if(!is.null(search)&&nzchar(search)) keep<-keep & apply(rows,1,function(x)any(grepl(tolower(search),tolower(x),fixed=TRUE),na.rm=TRUE))
  rows[which(keep),,drop=FALSE]
}
