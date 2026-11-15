# Sigma Airlines: no API clients or private row data are loaded in this app.
source('bootstrap.R')
source('data.R'); source('plots.R'); source('poster.R')
library(shiny); library(bslib)
source_path <- Sys.getenv('SIGMA_DASHBOARD_DATA', file.path(project_root,'results','research','current.json'))
fallback <- 'data/baseline.json'
ui <- page_navbar(
  title = 'Sigma Airlines / Research', id = 'view', selected = 'Poster presentation',
  theme = bs_theme(version = 5, bg = '#f7f5ef', fg = '#172b36', primary = '#145e63', base_font = 'sans-serif'),
  header = tagList(tags$head(tags$link(rel = 'stylesheet',type = 'text/css',href = 'research.css')),
                   div(class = 'evidence-strip',textOutput('evidence_status'), actionButton('refresh','Refresh data'), downloadButton('poster_pdf','Export poster PDF'))),
  nav_panel('Poster presentation',
    div(class = 'poster',
      div(class = 'poster-title',p(class = 'eyebrow','SYSEN 5300 / SIX SIGMA RESEARCH'),
          h1('Can structured engineering coverage reduce missed failure modes?'),
          p('A controlled comparison of AI-generated FMEAs across five engineering systems.')),
      div(class = 'poster-evidence',uiOutput('poster_results')),
      layout_columns(plotOutput('coverage',height = '300px'),plotOutput('pareto',height = '300px'),col_widths = c(6,6)),
      div(class = 'poster-narrative',
          tags$section(h2('Data'),textOutput('baseline_caption'),p('Report aggregates and validated run-level observations remain separate.')),
          tags$section(h2('Method'),p('DMAIC Improve / Control. Independent input inventory, deterministic structural audit, unchanged external AI judge, sampled engineering review.'),p('Python computes additive ANOVA and system-stratified bootstrap 95% intervals.')),
          tags$section(h2('Discussion / implications'),p('Higher output volume is not proof of engineering quality. Track extra rows, correctness and provisional ratings alongside coverage.'),p('No improvement claim until comparable evaluated observations support it.'))),
      h2('V4 success criteria'),uiOutput('criteria'),
      p(class = 'caption','AI-assisted presentation draft. Students must verify findings, interpret evidence and write their own submitted prose.'))),
  nav_panel('Live experiment results',
    layout_sidebar(sidebar = sidebar(
      selectInput('versions','Skill versions',choices = c('v2.0','v3.0','v4.0'),selected = c('v2.0','v3.0','v4.0'),multiple = TRUE),
      selectInput('systems','Systems',choices = LETTERS[1:5],selected = LETTERS[1:5],multiple = TRUE),
      selectInput('run','Run',choices = 'All'),
      dateRangeInput('dates','Generation date',start = '2026-01-01',end = Sys.Date()),
      selectInput('eval_status','Evaluation status',choices = c('All','evaluated','awaiting_evaluation')),
      p('Filters select observations. Published confidence intervals and tests always describe the complete validated cohort.')),
      h1('Live experiment results'),uiOutput('pending_versions'),plotOutput('run_plot'),plotOutput('overall'),
      h2('Version summary'),tableOutput('version_summary'),h2('System summary'),tableOutput('system_summary'),
      h2('Statistical results'),verbatimTextOutput('statistics'),h2('Selected observations'),tableOutput('run_table'))),
  nav_panel('Failure-mode analysis',h1('Where coverage breaks down'),plotOutput('pareto_detail'),
            h2('Component coverage and quality guardrails'),tableOutput('coverage_table'),
            h2('Extra unmatched rows'),tableOutput('extras'),h2('Engineering review'),tableOutput('review')),
  nav_panel('Experiment explorer',h1('Experiment explorer'),p('Safe metadata only. Generated FMEA rows, reference text and private judge notes are excluded.'),tableOutput('registry')),
  nav_panel('Methodology',h1('Research method'),
    h2('Define / Measure / Analyze'),p('Quantity of interest: missed failure-mode opportunities per evaluated run, with separate pooled counts. The V2 report establishes a pooled historical baseline; it cannot reconstruct independent run observations.'),
    h2('Improve'),p('Remote V3 introduced prompt-based unit and failure-type checks. The complementary local V3 audit emitted structured links. V4 adds an independent input inventory, deterministic gap audit and targeted remediation preparation.'),
    h2('Control'),p('Freeze model settings, package hashes, judge v1.2 and human reference revisions. Validate every receipt and judge import. Preserve original AI decisions alongside engineer review and adjudication.'),
    h2('Inference and limitations'),p('Primary: V2 versus V4. Additive model: missed_percentage ~ skill_version + system. Independent-run bootstrap within version/system retains equal system weights. At least two runs per cell are needed for intervals; four planned runs per cell still yield limited precision.'),
    p('Sigma is inverse-normal yield plus the conventional 1.5 shift, not a certification. Bounded percentages, variance, independence and additive-model assumptions need review. Canonical package 0.3 is a different workflow and is excluded.'),
    h2('Validation / approval'),p('Schema validity, model completeness claims and engineering acceptance are distinct. No live evaluations are fabricated. Public hosting and sanitized-data publication require explicit approval.')),
  footer = div(class = 'footer',textOutput('snapshot_status'))
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
    if (is.null(value) || !is.finite(value) || value < 1) 900 else max(300,value)
  }
  responsive_plot <- function(plot,id) {
    if (width_for(id)() < 600) {
      wrap <- function(x) paste(strwrap(x,width=36),collapse='\n')
      plot <- plot + labs(title=wrap(plot$labels$title),subtitle=wrap(plot$labels$subtitle),caption=wrap(plot$labels$caption)) + research_theme(11)
    }
    plot
  }
  output$coverage <- renderPlot(responsive_plot(coverage_plot(data()),'coverage'),res=120,width=width_for('coverage'),height=300)
  output$pareto <- renderPlot(responsive_plot(pareto_plot(data()),'pareto'),res=120,width=width_for('pareto'),height=300)
  output$pareto_detail <- renderPlot(responsive_plot(pareto_plot(data()),'pareto_detail'),res=120,width=width_for('pareto_detail'),height=300)
  output$overall <- renderPlot(responsive_plot(overall_plot(data()),'overall'),res=120,width=width_for('overall'),height=300)
  output$criteria <- renderUI({criteria <- data()$statistics$criteria; div(class='criteria-grid',lapply(names(criteria),function(k) div(strong(criteria[[k]]),span(gsub('_',' ',k)))))})
  output$pending_versions <- renderUI({
    available <- unique(as_table(data()$runs)$skill_version)
    p(paste(paste(setdiff(c('v2.0','v3.0','v4.0'),available),'Pending Evaluation'),collapse=' | '))
  })
  observe({
    registry <- as_table(data()$registry)
    updateSelectInput(session,'run',choices=c('All',if(nrow(registry)) registry$run_id))
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
  output$run_plot <- renderPlot({if(nrow(filtered())) coverage_plot(data(),filtered()) else coverage_plot(data(),data.frame())},res=120,width=width_for('run_plot'),height=300)
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
}
shinyApp(ui,server)
