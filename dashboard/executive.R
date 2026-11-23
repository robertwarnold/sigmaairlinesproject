coverage_change <- function(records) {
  before <- records[['v2.0']]; after <- records[['v3.0']]
  if(is.null(before)||is.null(after)) return(NULL)
  100*(before$pooled_missed_rate-after$pooled_missed_rate)
}

quality_reasons <- function(snapshot,filters) {
  panel_filters <- Filter(Negate(is.null),lapply(filters[setdiff(names(filters),c('skill','round'))],scope_value))
  if(length(panel_filters)) return(data.frame())
  rows <- as_table(snapshot$pareto)
  skill <- scope_value(filters$skill); round <- scope_value(filters$round)
  if(nrow(rows) && is.null(round)) {
    if(!is.null(skill)) rows <- rows[which(rows$skill_version==skill),,drop=FALSE]
    if(nrow(rows)) {
      version <- tail(sort(unique(rows$skill_version)),1)
      rows <- rows[which(rows$skill_version==version),,drop=FALSE]
      return(rows[order(-rows$count,rows$miss_category),,drop=FALSE])
    }
  }
  if((!is.null(skill)&&skill!='v2.0') || (!is.null(round)&&round!='1')) return(data.frame())
  counts <- unlist(snapshot$baseline$miss_categories)
  if(!length(counts)) return(data.frame())
  rows <- data.frame(miss_category=names(counts),count=as.numeric(counts),
    percentage=100*as.numeric(counts)/snapshot$baseline$missed,skill_version='Historical V2.0 report')
  rows[order(-rows$count,rows$miss_category),,drop=FALSE]
}

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
    change <- coverage_change(records)
    direction <- if(change>0) 'rose' else if(change<0) 'fell' else 'held steady'
    sprintf('Historical reference coverage %s from %s to %s. Unmatched findings still require engineering review.',
      direction,pct(1-before$pooled_missed_rate),pct(1-after$pooled_missed_rate))
  })
  latest_evidence <- reactive({
    records <- evidence()
    version <- tail(names(records),1)
    if(length(version)) list(version=version,metrics=records[[version]])
  })
  output$executive_metrics <- renderUI({
    latest <- latest_evidence()
    f <- financial()
    div(class='evidence-kpis evidence-kpis-stack',
      evidence_kpi('Modeled first-year net benefit',number_text(f$modeled$first_year_net_savings,'$',0),
        if(is.null(f)) 'Scenario unavailable' else workspace_link('finance',sprintf('Scenario at %s FMEAs/year',f$assumptions$annual_volume)),'coins'),
      evidence_kpi('Modeled unit cost reduction',if(is.null(f$modeled$percentage_reduction)) 'Unavailable' else sprintf('%.1f%%',f$modeled$percentage_reduction),
        if(is.null(f)) NULL else sprintf('%+.1f modeled labor hours saved per FMEA',f$assumptions$manual_hours-sum(f$activities$hours_per_fmea,na.rm=TRUE)),'percent'),
      evidence_kpi('Unmatched findings',if(is.null(latest)) 'Unavailable' else sprintf('%.1f per run',latest$metrics$mean_unmatched_generated_per_run),
        if(!is.null(latest)) paste(latest$version,'historical evaluation'),'list'),
      evidence_kpi('Independent validation','Pending',workspace_link('quality','Review evidence and limitations'),'shield-halved'))
  })
  output$executive_coverage <- renderUI({
    records <- evidence()
    if(!length(records)) return(p('Historical coverage is unavailable for this selection.'))
    coverage <- vapply(records,function(x) 100*(1-x$pooled_missed_rate),numeric(1))
    change <- coverage_change(records)
    latest <- latest_evidence()
    chart <- bar_rows(toupper(names(coverage)),coverage,100,display=sprintf('%.1f%%',coverage),
        colors=rep(c('#70b7f5','#0876c4'),length.out=length(coverage)))
    tagList(div(class='coverage-comparison',div(chart,div(class='coverage-axis',lapply(seq(0,100,20),function(x) span(paste0(x,'%'))))),
      if(!is.null(change)) div(class=paste('coverage-change',if(change>=0) 'positive' else ''),strong(sprintf('%+.1f pp',change)),span('V3 vs V2'))),
      p(class='chart-note',sprintf('%s: %d of %d reference opportunities found across %d runs.',
        latest$version,latest$metrics$opportunities-latest$metrics$missed,latest$metrics$opportunities,latest$metrics$runs)),
      tags$details(tags$summary('How coverage is calculated'),
        p('Identified opportunities divided by all reference opportunities in the archived comparison (historical-comparison-1). System, round and skill filters apply. Each run contributes its own opportunities.')),
      workspace_link('quality','View engineering evidence'))
  })
  output$executive_findings <- renderUI({
    records <- evidence()
    v3 <- records[['v3.0']]
    decision <- function(title,body,route,link) tags$section(h3(title),p(body),workspace_link(route,link))
    div(class='decision-grid',
      decision('What improved',if(!is.null(coverage_change(records))) sprintf('Pooled historical coverage changed by %+.1f percentage points from V2 to V3.',coverage_change(records))
        else 'A V2-to-V3 comparison requires both historical cohorts.','quality','Coverage evidence'),
      decision('What remains uncertain',if(!is.null(v3)) sprintf('V3 averaged %.1f unmatched findings per run. Their validity requires adjudication.',v3$mean_unmatched_generated_per_run)
        else 'Unmatched findings and rating accuracy require independent validation.','explorer','Open evidence register'),
      decision('Recommended next action','Adjudicate unmatched findings, verify severity, and collect paired engineering labor logs.','finance','Review scenario assumptions'))
  })
  output$quality_metrics <- renderUI({
    latest <- latest_evidence()
    rate <- data()$baseline$judge_repeatability_reported$agreement
    div(class='evidence-kpis quality-kpis',
      evidence_kpi('Reference coverage',if(is.null(latest)) 'Unavailable' else pct(1-latest$metrics$pooled_missed_rate),latest$version,'crosshairs'),
      evidence_kpi('Missed opportunities',if(is.null(latest)) 'Unavailable' else latest$metrics$missed,
        if(!is.null(latest)) sprintf('of %d (%s)',latest$metrics$opportunities,latest$version),'list'),
      evidence_kpi('Unmatched generated rows',if(is.null(latest)) 'Unavailable' else sprintf('%.1f',latest$metrics$mean_unmatched_generated_per_run),'Per evaluated run','layer-group'),
      evidence_kpi('Judge repeatability',if(is.null(rate)) 'Unavailable' else pct(rate),'Historical reported trial agreement','people-group'),
      evidence_kpi('Independent accuracy','Unverified','Needs adjudicated reference evidence','shield-halved'))
  })
  reasons <- reactive(quality_reasons(data(),workspace_filters(input)))
  output$pareto_detail <- renderUI({
    rows <- reasons()
    if(!nrow(rows)) return(p('Missed-reason counts are unavailable for this selection. Select the published cohort or import classified evidence.'))
    labels <- gsub('^([a-z])','\\U\\1',gsub('_',' ',rows$miss_category),perl=TRUE)
    count <- sum(rows$count)
    total <- if(identical(rows$skill_version[1],'Historical V2.0 report')) data()$baseline$missed else count
    tagList(p(class='chart-note',sprintf('%s | %s classified misses of %s',rows$skill_version[1],count,total)),
      bar_rows(labels,rows$count,max(1,rows$count),display=sprintf('%d (%.1f%%)',rows$count,rows$percentage),colors=rep('#1686cf',nrow(rows))))
  })
  output$quality_findings <- renderUI({
    rows <- head(reasons(),3)
    if(!nrow(rows)) return(p('Ranked findings require missed-opportunity classifications for this cohort.'))
    implications <- c(repeated_unit_skipped='Check that the analysis covers each repeated unit.',
      sub_case_not_split_out='Review whether distinct failure cases are represented separately.',
      part_never_covered='Check inventory and interface coverage.')
    findings <- lapply(seq_len(nrow(rows)),function(i) {
      category <- rows$miss_category[i]
      key <- gsub('[^a-z0-9]+','_',tolower(category))
      tags$li(strong(gsub('_',' ',category)),
        span(sprintf('%d classified misses (%.1f%%)',rows$count[i],rows$percentage[i])),
        if(key %in% names(implications)) span(implications[[key]]))
    })
    tagList(p(class='chart-note',rows$skill_version[1]),tags$ol(class='quality-findings',findings),
      workspace_link('experiments','Review experiment provenance'))
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
    by_system <- do.call(rbind,lapply(options,function(system) {
      group <- select_historical_scope(historical(),system,scope_value(input$g_skill),scope_value(input$g_round))$metrics
      do.call(rbind,lapply(names(group),function(version) {
        item <- group[[version]]
        data.frame(System=system,Skill=version,Runs=item$runs,Missed=item$missed,
          Opportunities=item$opportunities,Coverage=pct(1-item$pooled_missed_rate))
      }))
    }))
    chart_panel('Historical reference coverage',tagList(div(class='quality-table',chart_details(rows,'Coverage denominators')),
      if(nrow(as_table(by_system))) div(class='quality-table',chart_details(by_system,'Coverage by system')),
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
  for(id in c('executive_headline','executive_coverage','executive_findings','executive_metrics',
              'quality_metrics','pareto_detail','quality_findings','quality_coverage','quality_agreement'))
    outputOptions(output,id,suspendWhenHidden=FALSE)
}
