executive_server <- function(input,output,data,historical_metrics,financial,number_text,historical) {
  evidence <- reactive({
    metrics <- historical_metrics()$metrics
    if(length(metrics)) return(metrics)
    if(!is.null(input$g_system) && input$g_system!='All') return(NULL)
    if(!is.null(input$g_skill) && !input$g_skill %in% c('All','v2.0')) return(NULL)
    if(!is.null(input$g_round) && !input$g_round %in% c('All','1')) return(NULL)
    baseline <- data()$baseline
    if(!isTRUE(baseline$opportunities>0)) return(NULL)
    list('v2.0'=list(opportunities=baseline$opportunities,missed=baseline$missed,runs=baseline$total_runs,
      pooled_missed_rate=baseline$missed/baseline$opportunities,
      mean_unmatched_generated_per_run=baseline$extra_unmatched_rows/baseline$total_runs))
  })
  pct <- function(x) sprintf('%.1f%%',100*x)
  output$executive_headline <- renderText({
    records <- evidence(); before <- records[['v2.0']]; after <- records[['v3.0']]
    if(is.null(before)||is.null(after)) return('Select both historical cohorts to compare reference coverage.')
    change <- 100*(before$pooled_missed_rate-after$pooled_missed_rate)
    direction <- if(change>0) 'rose' else if(change<0) 'fell' else 'held steady'
    sprintf('Pooled reference coverage %s from %s to %s between V2 and V3 in this historical scope.',
      direction,pct(1-before$pooled_missed_rate),pct(1-after$pooled_missed_rate))
  })
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
      card('Estimated engineering time saved',if(is.null(hours)) 'Unavailable' else sprintf('%+.1f h / FMEA',hours),
        'Modeled labor hours saved per FMEA. Paired labor measurement is pending.','finance','View effort assumptions'),
      card('Modeled financial benefit',if(is.null(f)) 'Unavailable' else number_text(f$modeled$first_year_net_savings,'$',0),
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
      tags$details(tags$summary('How coverage is calculated'),
        p('Identified opportunities divided by all reference opportunities in the archived comparison (historical-comparison-1). System, round and skill filters apply. Each run contributes its own opportunities.')),
      workspace_link('quality','View coverage and denominators'))
  })
  output$executive_findings <- renderUI({
    records <- evidence()
    v2 <- records[['v2.0']]; v3 <- records[['v3.0']]
    tags$ol(class='executive-findings',
      if(!is.null(v2)&&!is.null(v3)) tags$li(sprintf('V3 pooled coverage was %.1f percentage points higher than V2 in the archived comparison.',
        100*(v2$pooled_missed_rate-v3$pooled_missed_rate)),' ',workspace_link('quality','Coverage evidence')),
      tags$li(if(!is.null(v2)&&!is.null(v3)) sprintf('Unmatched rows averaged %.1f per V3 run and %.1f per V2 run. Their disposition needs engineering review. ',
        v3$mean_unmatched_generated_per_run,v2$mean_unmatched_generated_per_run) else 'Comparable unmatched-row counts require both historical cohorts. ',
        workspace_link('quality','Inspect quality evidence')),
      tags$li('Confirm severity and collect paired labor logs before relying on the scenario for a budget decision. ',
        workspace_link('finance','Inspect scenario inputs')))
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
    filters <- workspace_filters(input)
    scoped <- any(vapply(filters[setdiff(names(filters),'skill')],function(x) !is.null(scope_value(x)),logical(1)))
    if(scoped) return(div(class='workspace-empty',strong('Judge field agreement is unavailable for this scope'),
      p('The published totals support skill filtering. Other selections require item-level denominators.')))
    selected <- as_table(data()$field_accuracy)
    if(nrow(selected) && !is.null(input$g_skill) && input$g_skill!='All') selected <- selected[selected$skill_version==input$g_skill,,drop=FALSE]
    if(nrow(selected)) selected <- selected[selected$denominator>0,,drop=FALSE]
    if(!nrow(selected)) return(div(class='workspace-empty',strong('Judge agreement requires item-level evidence'),
      p('Import an identifier-only judge export with scorable matched pairs.')))
    labels <- c(cause_correct='Cause',end_effect_correct='System effect',severity_difference='Severity within 1',
      occurrence_difference='Occurrence within 1',detection_difference='Detection within 1',rpn_relative_difference='RPN within 25%')
    selected$field <- unname(labels[selected$field])
    chart_panel('Judge field agreement',tagList(p('Published cohort by skill. Denominators count scorable matched items.'),chart_details(selected,'Agreement and denominators')))
  })
}
