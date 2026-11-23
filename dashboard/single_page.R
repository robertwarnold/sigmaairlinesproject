# Application shell and shared filter projections.
chart_tokens <- list(background='#f7f8fa',surface='#ffffff',raised='#eef2f5',ink='#33414c',
  muted='#65737e',accent='#387fb5',grid='#e0e5e9',warning='#9c6525',failure='#c85360')
palette <- c('v2.0'='#697b8a','v3.0'='#8d78b4','v3.0-audit'='#af782c','v4.0'='#387fb5')
analytics_card <- function(title,id,note=NULL) chart_panel(title,uiOutput(id),note)
workspace_views <- c(overview='Executive Overview',quality='Engineering Quality',
  experiments='Experiments & Performance',finance='Financial Impact',explorer='Data Explorer')
workspace_link <- function(view,label=workspace_views[[view]],...) tags$a(href=paste0('#',view),label,...)
workspace_view <- function(view,description,...) tags$section(id=view,class='workspace-view',
  hidden=if(view!='overview') NA else NULL,`aria-labelledby`=paste0(view,'-title'),
  div(class='view-heading',h1(id=paste0(view,'-title'),tabindex='-1',workspace_views[[view]]),p(description)),...)
analytics_ui <- function(defaults) {
  page_fluid(theme=bs_theme(version=5,bg=chart_tokens$background,fg=chart_tokens$ink,primary=chart_tokens$accent,base_font='sans-serif'),
    tags$head(tags$title('Sigma Airlines | FMEA Engineering Dashboard'),chart_css_tokens(),tags$link(rel='stylesheet',href='research.css'),tags$link(rel='stylesheet',href='single-page.css'),
      tags$link(rel='stylesheet',href='workspace-v43.css'),
      tags$link(rel='stylesheet',href='workspace-v44.css'),
      tags$script(src='presentation.js'),tags$script(src='charts.js'),tags$script(src='single-page.js'),tags$script(src='workspace-v43.js',defer=NA)),
    tags$main(class='analytics-page',
      tags$header(class='analytics-header',div(class='workspace-brand',strong('Sigma Airlines'),span('FMEA Engineering Intelligence')),
        div(uiOutput('judge_import_action',inline=TRUE),actionButton('refresh','Refresh'),actionButton('generation_help','Generate FMEA'))),
      tags$nav(class='workspace-nav',`aria-label`='Primary navigation',
        lapply(names(workspace_views),function(view) workspace_link(view,`aria-current`=if(view=='overview') 'page' else NULL))),
      tags$label(class='workspace-mobile-nav',span('View'),tags$select(id='workspace-view-select',`aria-label`='View',
        lapply(names(workspace_views),function(view) tags$option(value=view,workspace_views[[view]])))),
      div(class='scope-bar',`aria-live`='polite',textOutput('active_analysis_filters'),textOutput('scope_evidence')),
      tags$details(class='workspace-filters',tags$summary('Analysis filters'),
      div(class='global-filters',selectInput('g_run','Experiment / run',choices='All'),selectInput('g_system','System',choices='All'),
        selectInput('g_subsystem','Subsystem',choices='All'),selectInput('g_model','Model / provider',choices='All'),
        selectInput('g_skill','Skill version',choices='All'),selectInput('g_round','Experiment round',choices='All'),
        selectInput('g_judge','Judge version',choices='All'),dateRangeInput('g_dates','Generation date',start='2020-01-01',end=Sys.Date()),
        selectInput('g_review','Engineering review',choices=c('All','NEEDS_REVIEW','APPROVED','REJECTED')),actionButton('global_reset','Reset filters'))),
      tags$details(class='workspace-provenance',tags$summary('Data provenance'),uiOutput('analytics_context'),textOutput('snapshot_status')),
      workspace_view('overview',textOutput('executive_headline',inline=TRUE),
        uiOutput('executive_metrics'),
        div(class='executive-grid',
          chart_panel('Coverage across study rounds',uiOutput('executive_coverage')),
          chart_panel('Key engineering findings',uiOutput('executive_findings')))),
      workspace_view('quality','Assess reference coverage, rating agreement and records that need review.',
      uiOutput('quality_coverage'),
      uiOutput('quality_agreement'),
      tags$details(class='support-details',tags$summary('Missed reasons and supporting evidence'),uiOutput('pareto_detail')),
      tags$details(class='support-details',tags$summary('Engineering validation and risk distribution'),
      tags$section(id='health',h2('FMEA health at a glance'),uiOutput('analytics_health'),
        div(class='attention-card',h3('What needs attention'),uiOutput('analytics_attention'))),
      tags$section(id='risk-analysis',h2('Failure modes and risk distribution'),
        div(class='analytics-grid',analytics_card('Failure modes by subsystem','analytics_subsystems'),analytics_card('Severity versus occurrence','analytics_matrix'),
          analytics_card('RPN distribution','analytics_rpn'),analytics_card('Failure causes by category','analytics_causes'),
          chart_panel('Highest-priority failure modes',tagList(selectInput('priority_order','Order',choices=c('Severity first'='severity','RPN first'='RPN'),width='150px'),uiOutput('analytics_priority'))),
          analytics_card('Corrective action status','analytics_actions')))),
      workspace_link('explorer','Open the evidence register')),
      workspace_view('experiments','Trace generation timing, independent evaluations and workflow provenance.',
        analytics_card('Generation time by system and skill','analytics_duration'),
        chart_panel('Generation registry',tagList(div(class='finance-controls',
          selectInput('generation_filter','Run status',choices=c('All','success','failed','running','planned')),
          selectInput('generation_sort','Sort runs',choices=c('Most recent'='recent','System and round'='identity','Longest generation'='duration'))),
          uiOutput('explorer_table'),numericInput('run_page','Page',1,min=1,width='6rem'),
          tags$details(id='run-detail',tags$summary('Selected generation'),uiOutput('generation_detail'),tableOutput('event_table')))),
      tags$details(id='ai-performance',class='support-details',tags$summary('Performance diagnostics'),
        analytics_card('Generation and evaluation activity','mission_activity'),
        div(class='analytics-grid',analytics_card('Skill version performance','analytics_versions','Structural validation and engineering decisions; not reference recall.'),
          analytics_card('Evidence quality','analytics_evidence'),
          analytics_card('Scoring agreement','analytics_agreement','Explicit human rating corrections only / within \u00b11 / at least two pairs per rating.')),
        div(class='analytics-grid three',analytics_card('Duplicate and validation rates by run','analytics_trends'),
          analytics_card('Independent evaluation','analytics_judge')),
        chart_panel('Experiment summary',uiOutput('analytics_experiments')),
        chart_panel('Historical V2.0 and V3.0 comparison',tagList(tableOutput('historical_comparison'),uiOutput('historical_export_action')),
          'Descriptive results from the archived run-level CSV. Equal-system means give each system the same weight.'),
        tags$details(class='support-details',tags$summary('GitHub run registry, provenance and lifecycle'),
          uiOutput('experiment_progress'),textOutput('sync_summary'),tableOutput('workflow_table')))),
      workspace_view('finance','Compare planning scenarios and review the available spending and labor evidence.',
        p(class='finance-context','Planning scenario · based on the research snapshot and editable assumptions. Record filters do not change the scenario.'),
        div(class='finance-controls',selectInput('finance_preset','Planning scenario',choices=c('Baseline','Conservative','Optimistic')),
          downloadButton('finance_export','Export scenario CSV'),downloadButton('finance_brief','Export decision brief')),
        uiOutput('financial_metrics'),div(class='analytics-grid',analytics_card('Manual and AI-assisted cost per FMEA','finance_cost'),analytics_card('AI-assisted cost composition','finance_breakdown')),
        tags$details(tags$summary('Assumptions and sensitivity'),div(class='assumption-grid',lapply(names(defaults),function(k) {
          if(k=='uncertainty_fraction') sliderInput(paste0('fin_',k),gsub('_',' ',k),min=0,max=.6,value=defaults[[k]],step=.05)
          else numericInput(paste0('fin_',k),gsub('_',' ',k),defaults[[k]],min=if(k=='success_probability') .01 else if(k=='annual_volume') 1 else 0,
            max=if(k=='success_probability') 1 else NA)
        })),actionButton('reset_finance','Reset assumptions'),uiOutput('finance_sensitivity'),uiOutput('finance_distribution')),
        tags$details(class='support-details',tags$summary('Observed API spending'),uiOutput('finance_spending')),
        textOutput('financial_status'),tags$details(tags$summary('Inputs, formulas and provenance'),uiOutput('finance_provenance'),
          tableOutput('finance_inputs'),tableOutput('historical_finance'),tableOutput('observed_costs'))),
      workspace_view('explorer','Inspect generated rows, record engineering decisions and export evidence.',
      tags$section(id='fmea-register',h2('Detailed FMEA register'),engineering_ui()),
      tags$details(class='support-details',tags$summary('Research methods, historical baseline and academic exports'),
        p('Generator output, structural validation, source-supported evidence, human review and independent reference evaluation are separate evidence layers.'),
        p('Ratings use the existing integer 1\u201310 policy. S \u2265 9 is a visibility threshold, not a formal risk acceptance criterion. Dashboard V4.1/V4.2 revisions do not imply new FMEA skill versions.'),
        p('System, round and skill filter the historical comparison. Generation and private record filters apply when the relevant metadata is available. The frozen report and academic poster show their published cohort.'),
        uiOutput('historical_reference'),tableOutput('historical_baseline'),verbatimTextOutput('statistics'),uiOutput('criteria'),
        div(class='presentation-actions',actionButton('presentation_toggle','Present fullscreen'),downloadButton('poster_pdf','Export poster PDF')),
        div(class='poster',div(class='poster-title',h2('Can structured engineering coverage reduce missed failure modes?')),
          uiOutput('poster_results'),div(class='analytics-grid',plotOutput('coverage',height='270px'),plotOutput('pareto',height='270px')),
          div(class='poster-narrative',tags$section(h3('Data'),textOutput('baseline_caption')),tags$section(h3('Method'),p('DMAIC / independent evaluation / additive ANOVA and system-stratified bootstrap when supported.')),
            tags$section(h3('Discussion'),p('No improvement claim until comparable evaluated observations support it. Higher output volume is not proof of quality.')))),
        tags$details(tags$summary('Presenter notes'),p('Explain the question and five-system design, separate the V2 report from observed runs, distinguish structural checks from engineering approval, and report V4 evaluation as pending when applicable.')))),
      tags$footer('Private source records never enter the public research snapshot. Model calls require separate authorization.')))
}

# Pure projection shared by operational tables; research calculations remain Python-owned.
canonical_system <- function(value) sub('^system_','',value,ignore.case=TRUE)
filter_generation_rows <- function(rows,filters) {
  if(!nrow(rows)) return(rows)
  keep <- rep(TRUE,nrow(rows))
  for(pair in list(c('run','run_id'),c('system','system'),c('model','generator_model'),c('skill','skill_version'),
    c('round','resolved_round'),c('judge','judge_skill_version'))) {
    value <- filters[[pair[1]]]
    if(!is.null(value)&&value!='All') {
      match <- if(pair[2] %in% names(rows)) !is.na(rows[[pair[2]]]) & rows[[pair[2]]]==value else rep(FALSE,nrow(rows))
      if(pair[1]=='run' && 'engineering_run_id' %in% names(rows)) match <- match | (!is.na(rows$engineering_run_id) & rows$engineering_run_id==value)
      keep <- keep & match
    }
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
  fields<-c(run='run_id',system='system',subsystem='subsystem',model='generator_model',skill='skill_version',
    round='resolved_round',judge='judge_skill_version',review='review_status',severity='severity',occurrence='occurrence')
  for(key in names(fields)) {
    value<-filters[[key]]
    if(!is.null(value)&&value!='All') {
      observed <- if(fields[[key]] %in% names(rows)) as.character(rows[[fields[[key]]]]) else rep(NA_character_,nrow(rows))
      if(key=='system') observed <- canonical_system(observed)
      keep <- keep & !is.na(observed) & observed==value
    }
  }
  if(!is.null(filters$dates)) {
    dates<-as.Date(substr(rows$generation_timestamp,1,10));keep<-keep & !is.na(dates) & dates>=filters$dates[1] & dates<=filters$dates[2]
  }
  if(!is.null(focus)) keep<-keep & rows$record_id %in% focus
  if(!is.null(search)&&nzchar(search)) keep<-keep & apply(rows,1,function(x)any(grepl(tolower(search),tolower(x),fixed=TRUE),na.rm=TRUE))
  rows[which(keep),,drop=FALSE]
}
