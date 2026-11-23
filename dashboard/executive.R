executive_server <- function(input,output,data,historical_metrics,financial,number_text,historical) {
  evidence <- reactive({
    metrics <- historical_metrics()$metrics
    if(length(metrics)) return(metrics)
    if(!is.null(input$g_system) && input$g_system!='All') return(NULL)
    if(!is.null(input$g_skill) && !input$g_skill %in% c('All','v2.0')) return(NULL)
    baseline <- data()$baseline
    if(!isTRUE(baseline$opportunities>0)) return(NULL)
    list('v2.0'=list(opportunities=baseline$opportunities,missed=baseline$missed,runs=baseline$total_runs,
      pooled_missed_rate=baseline$missed/baseline$opportunities,
      mean_unmatched_generated_per_run=baseline$extra_unmatched_rows/baseline$total_runs))
  })
  pct <- function(x) sprintf('%.1f%%',100*x)
  card <- function(label,value,basis,view,link) tags$article(class='executive-metric',
    h2(label),strong(value),tags$small(basis),workspace_link(view,link))
  output$executive_metrics <- renderUI({
    records <- evidence()
    version <- tail(names(records),1)
    latest <- if(length(version)) records[[version]] else NULL
    f <- financial()
    hours <- if(!is.null(f)) f$assumptions$manual_hours-sum(f$activities$hours_per_fmea,na.rm=TRUE)
    repeatability <- data()$baseline$judge_repeatability_reported$agreement
    div(class='executive-metrics',
      card('Engineering coverage',if(is.null(latest)) 'Unavailable' else pct(1-latest$pooled_missed_rate),
        if(is.null(latest)) 'No historical cohort for this selection.' else sprintf('%s: %d of %d reference opportunities found.',version,latest$opportunities-latest$missed,latest$opportunities),
        'quality','Review coverage'),
      card('Review burden',if(is.null(latest)) 'Unavailable' else sprintf('%.1f rows',latest$mean_unmatched_generated_per_run),
        if(is.null(latest)) 'Requires a historical cohort.' else sprintf('%s unmatched rows per run across %d runs.',version,latest$runs),'quality','Review quality'),
      card('Engineering time',if(is.null(hours)) 'Unavailable' else sprintf('%+.1f h / FMEA',hours),
        'Modeled labor hours saved per FMEA. Paired labor measurement is pending.','finance','View effort assumptions'),
      card('Financial impact',if(is.null(f)) 'Unavailable' else number_text(f$modeled$first_year_net_savings,'$',0),
        if(is.null(f)) 'Scenario calculation unavailable.' else sprintf('Modeled first-year net benefit at %s FMEAs/year.',f$assumptions$annual_volume),
        'finance','View financial model'),
      card('Judge repeatability',if(is.null(repeatability)) 'Unavailable' else pct(repeatability),
        'Historical reported trial agreement. Independent accuracy and current-cohort repeatability are unverified.',
        'quality','Inspect judge evidence'))
  })
  output$executive_coverage <- renderUI({
    records <- evidence()
    if(!length(records)) return(p('Historical coverage is unavailable for this selection.'))
    coverage <- vapply(records,function(x) 100*(1-x$pooled_missed_rate),numeric(1))
    tagList(bar_rows(names(coverage),coverage,100,display=sprintf('%.1f%%',coverage)),
      p(class='chart-note','Pooled share of reference opportunities identified. Historical study evidence responds to system and skill filters.'),
      workspace_link('quality','View coverage and denominators'))
  })
  output$executive_findings <- renderUI({
    records <- evidence()
    v2 <- records[['v2.0']]; v3 <- records[['v3.0']]
    f <- financial()
    tags$ol(class='executive-findings',
      if(!is.null(v2)&&!is.null(v3)) tags$li(sprintf('V3 pooled coverage was %.1f percentage points higher than V2 in the archived comparison.',
        100*(v2$pooled_missed_rate-v3$pooled_missed_rate)),' ',workspace_link('quality','Coverage evidence')),
      if(!is.null(v2)&&!is.null(v3)) tags$li(sprintf('Unmatched rows averaged %.1f per V3 run and %.1f per V2 run. Engineering review determines their disposition.',
        v3$mean_unmatched_generated_per_run,v2$mean_unmatched_generated_per_run)),
      tags$li('Current technical credibility depends on independent evaluation and human acceptance. ',workspace_link('experiments','View experiment status')),
      if(!is.null(f)) tags$li('Estimated value depends on manual effort, review time and workload. ',
        if(grepl('historical V2',f$basis,fixed=TRUE)) 'The scenario uses historical V2 review counts. ',
        workspace_link('finance','Inspect scenario inputs')))
  })
  output$executive_decision <- renderUI({
    records <- evidence()
    p(class='executive-decision',if(all(c('v2.0','v3.0') %in% names(records)))
      'The historical study supports further evaluation of the coverage gain. Review unmatched rows, confirm severity against the engineering rubric, and log paired manual and AI-assisted labor before using the scenario as a budget commitment.'
      else 'Establish comparable coverage evidence for this selection. Record engineering dispositions and paired labor observations before using the scenario as a budget commitment.')
  })
  output$quality_coverage <- renderUI({
    records <- evidence()
    if(!length(records)) return(chart_panel('Reference coverage',p('No historical evidence for the selected cohort.')))
    rows <- do.call(rbind,lapply(names(records),function(version) {
      v <- records[[version]]
      data.frame(Skill=version, Runs=v$runs,Found=v$opportunities-v$missed,Missed=v$missed,
        Opportunities=v$opportunities,Coverage=pct(1-v$pooled_missed_rate),Unmatched_per_run=round(v$mean_unmatched_generated_per_run,1))
    }))
    systems <- names(historical()$metrics_by_system)
    selected <- if(is.null(input$g_system)) 'All' else input$g_system
    options <- if(selected=='All') systems else selected
    chart_panel('Historical reference coverage',tagList(div(class='quality-table',chart_details(rows,'Coverage denominators')),
      if(length(options)) div(class='quality-systems',lapply(options,function(system)
        workspace_link('experiments',paste('System',system,'experiments'),`data-open-system`=system))),
      workspace_link('experiments','Inspect the historical comparison')))
  })
  output$quality_agreement <- renderUI({
    selected <- as_table(data()$field_accuracy)
    if(nrow(selected) && !is.null(input$g_skill) && input$g_skill!='All') selected <- selected[selected$skill_version==input$g_skill,,drop=FALSE]
    if(nrow(selected)) selected <- selected[selected$denominator>0,,drop=FALSE]
    if(!nrow(selected)) return(p('Scorable matched pairs are pending for this selection.'))
    labels <- c(cause_correct='Cause',end_effect_correct='System effect',severity_difference='Severity within 1',
      occurrence_difference='Occurrence within 1',detection_difference='Detection within 1',rpn_relative_difference='RPN within 25%')
    selected$field <- unname(labels[selected$field])
    tagList(p('Snapshot cohort by skill. Each denominator counts scorable matched items.'),chart_details(selected,'Agreement and denominators'))
  })
}
