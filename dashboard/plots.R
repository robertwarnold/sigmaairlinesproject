# Presentation figures only display Python-computed quantities and intervals.
library(ggplot2)
source(file.path(if(file.exists('dashboard/theme.R')) 'dashboard' else '.', 'theme.R'))
research_theme <- function(size = 15) {
  theme_minimal(base_size = size) + theme(
    plot.background = element_rect(fill = chart_tokens$surface, colour = NA),
    panel.background = element_rect(fill = chart_tokens$surface, colour = NA),
    panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
    panel.grid.major.y = element_line(colour=chart_tokens$grid,linewidth=.25), text=element_text(colour=chart_tokens$muted), legend.text=element_text(colour=chart_tokens$muted), legend.title=element_text(colour=chart_tokens$muted),
    plot.title = element_text(face = 'bold', colour = chart_tokens$ink),
    plot.subtitle = element_text(colour = chart_tokens$muted), legend.position = 'bottom', strip.text=element_text(colour=chart_tokens$muted),
    axis.text = element_text(colour = chart_tokens$muted))
}
coverage_plot <- function(data, selected = NULL) {
  runs <- if (is.null(selected)) as_table(data$runs) else selected
  if (!nrow(runs) && !is.null(selected)) return(ggplot() + annotate('text',x=0,y=0,label='No evaluated observations match the filters',size=5,colour=chart_tokens$muted) + research_theme() + theme(axis.text=element_blank(),axis.title=element_blank(),panel.grid=element_blank()))
  if (!nrow(runs)) {
    # A single aggregate report point is never portrayed as run-level evidence.
    return(ggplot(data.frame(version = 'V2 report aggregate', missed = data$baseline$pooled_missed_percentage_reported), aes(version, missed)) +
      geom_hline(yintercept = 20, linetype = 'dashed', colour = chart_tokens$warning) +
      geom_point(size = 5, colour = palette[['v2.0']]) +
      annotate('text', x = 1, y = 65, label = 'V3 and V4: Pending Evaluation\nRun-level confidence intervals unavailable', size = 5, colour=chart_tokens$muted) +
      scale_y_continuous(limits = c(0,100)) + labs(title = 'Failure-mode coverage comparison', subtitle = 'Report-derived V2 pooled rate; no evaluated V4 observations', x = NULL, y = 'Missed failure modes (%)', caption = 'Dashed line: V4 target below 20%. Aggregate point has no inferred CI.') + research_theme())
  }
  means <- as_table(data$per_system)
  if (nrow(means)) means <- means[paste(means$skill_version,means$system) %in% paste(runs$skill_version,runs$system),,drop=FALSE]
  p <- ggplot(runs, aes(skill_version, missed_percentage, colour = skill_version)) +
    geom_hline(yintercept = 20, linetype = 'dashed', colour = chart_tokens$warning) +
    geom_point(position = position_jitter(width = .08, seed = 5300), alpha = .7, size = 2.6) +
    facet_wrap(~system, nrow = 1) + scale_colour_manual(values = palette, drop = FALSE) +
    coord_cartesian(ylim = c(0,100)) + labs(title = 'Failure-mode coverage comparison',
      subtitle = 'Individual independent runs; system means and bootstrap 95% intervals',
      x = NULL, y = 'Missed failure modes (%)', colour = 'Skill version',
      caption = 'Intervals and means use the complete validated cohort; filters do not recompute inference.') + research_theme()
  if (nrow(means)) {
    p <- p + geom_errorbar(data = means, aes(x = skill_version, ymin = ci_low, ymax = ci_high, colour = skill_version), inherit.aes = FALSE, width = .12, na.rm = TRUE) +
      geom_point(data = means, aes(x = skill_version, y = mean_run_missed_percentage, colour = skill_version), inherit.aes = FALSE, shape = 18, size = 4)
  }
  p
}
pareto_plot <- function(data) {
  rows <- as_table(data$pareto)
  reported <- !nrow(rows)
  if (reported) {
    counts <- unlist(data$baseline$miss_categories)
    rows <- data.frame(miss_category = names(counts), count = as.numeric(counts), skill_version = 'v2.0 report')
    # Report-derived percentages are supplied by the authoritative snapshot.
    rows$percentage <- as.numeric(unlist(data$baseline$miss_category_percentages))
    rows$cumulative_percentage <- as.numeric(unlist(data$baseline$miss_category_cumulative_percentages))
  }
  rows <- rows[order(rows$skill_version,-rows$count),,drop=FALSE]
  rows$label <- paste0(rows$miss_category, '\n', sprintf('%.1f%%', rows$percentage))
  rows$label <- factor(rows$label, levels = unique(rows$label))
  max_count <- max(c(1,rows$count))
  ggplot(rows, aes(label, count)) + geom_col(fill = chart_tokens$accent, width = .65) +
    geom_line(aes(y = cumulative_percentage * max_count/100, group = skill_version), colour = chart_tokens$warning, linewidth = .8) +
    geom_point(aes(y = cumulative_percentage * max_count/100), colour = chart_tokens$warning, size = 2) +
    facet_wrap(~skill_version,scales = 'free_x') + scale_y_continuous(sec.axis = sec_axis(~ . * 100/max_count, name = 'Cumulative missed modes (%)')) +
    labs(title = 'Pareto: where failure modes were missed', subtitle = if (reported) 'V2 report-derived category totals; V3/V4 pending' else 'Validated item-level classifications; unclassified cases remain visible',
         x = NULL, y = 'Missed opportunities', caption = 'Categories are mutually exclusive. Counts and percentages come from Python.') +
    research_theme(13) + theme(axis.text.x = element_text(angle = 18, hjust = 1))
}
overall_plot <- function(data) {
  rows <- as_table(data$per_version)
  if (!nrow(rows)) return(coverage_plot(data))
  ggplot(rows,aes(skill_version, system_weighted_mean, colour = skill_version)) +
    geom_hline(yintercept = 20,linetype = 'dashed',colour = chart_tokens$warning) + geom_point(size = 4) +
    geom_errorbar(aes(ymin = ci_low,ymax = ci_high),width = .12,na.rm = TRUE) +
    scale_colour_manual(values = palette) + labs(title = 'Overall missed percentage', subtitle = 'Equal-system mean and system-stratified 95% interval; run mean shown separately', x = NULL,y = 'Missed (%)') + research_theme()
}
# Additional views reuse validated snapshot tables; no research statistics computed here.
empty_plot <- function(title,message='Pending Evaluation - no validated observations') ggplot() +
  annotate('text',x=0,y=0,label=message,colour=chart_tokens$muted,size=5) + labs(title=title) + research_theme() +
  theme(axis.text=element_blank(),axis.title=element_blank(),panel.grid=element_blank())
field_accuracy_plot <- function(data) {
  rows <- as_table(data$field_accuracy)
  if (!nrow(rows) || !any(!is.na(rows$accuracy_percentage))) {
    historical <- data$baseline$conditional_quality_reported
    if (is.null(historical)) return(empty_plot('Field-level accuracy'))
    rows <- data.frame(field=names(historical),accuracy_percentage=100*as.numeric(unlist(historical)),skill_version='V2 report aggregate')
    subtitle <- 'Historical report aggregates; matched-item denominators unavailable'
  } else {
    rows <- rows[!is.na(rows$accuracy_percentage),,drop=FALSE]
    subtitle <- 'Selected independent evaluations; observed matched-item denominators'
  }
  ggplot(rows,aes(field,accuracy_percentage,fill=skill_version)) + geom_col(position='dodge',width=.65) +
    coord_flip(ylim=c(0,100)) + scale_fill_manual(values=c(palette,'V2 report aggregate'='#a5b1bd')) + labs(title='Field-level accuracy',subtitle=subtitle,x=NULL,y='Agreement (%)',fill='Skill version') + research_theme(13)
}
activity_plot <- function(data) {
  rows <- as_table(data$operations$generation_activity)
  if (!nrow(rows)) return(empty_plot('Generation activity','No registered generation timestamps'))
  ggplot(rows,aes(as.Date(date),count,fill=generation_status)) +
    geom_col() + scale_fill_manual(values=c(success=chart_tokens$accent,failed=chart_tokens$failure,running=chart_tokens$warning,planned='#7d8c9b',queued='#b9a1e1')) +
    labs(title='Generation activity',subtitle='Python-counted actual receipts, not workflow execution counts',x='Generation start date',y='FMEA generation attempts',fill='Generation status') + research_theme(13)
}

completeness_plot <- function(data) {
  rows <- as_table(data$runs)
  if(!nrow(rows)) return(empty_plot('Quality versus output completeness'))
  ggplot(rows,aes(generated_rows,missed_percentage,colour=skill_version,shape=system)) + geom_point(size=3) +
    scale_colour_manual(values=palette) + labs(title='Quality versus output completeness',subtitle='Evaluated FMEAs only; association does not establish causation',
      x='Generated rows per FMEA',y='Missed reference opportunities (%)',colour='Skill version',shape='System') + research_theme(13)
}
financial_plot <- function(finance,kind='simulation') {
  if(is.null(finance)) return(empty_plot('Financial analysis','Scenario pending Python calculation'))
  if(kind=='simulation') {
    rows <- as_table(finance$simulation$histogram)
    return(ggplot(rows,aes(midpoint,count)) + geom_col(fill=chart_tokens$accent) + geom_vline(xintercept=0,colour=chart_tokens$failure,linetype='dashed') +
      geom_vline(xintercept=finance$simulation$median_annual_net_savings,colour=chart_tokens$warning) +
      labs(title='Modeled first-year net savings',subtitle=sprintf('10,000 assumption-driven draws\n95%% simulation interval $%.0f to $%.0f',finance$simulation$interval95_annual_usd[1],finance$simulation$interval95_annual_usd[2]),
           x='Annual net savings (USD; negative values retained)',y='Simulation draws') + research_theme(13))
  }
  if(kind=='comparison') {
    rows <- data.frame(method=c('Manual','AI-assisted'),annual_cost=c(finance$modeled$manual_annual_cost,finance$modeled$ai_annual_operating_cost))
    return(ggplot(rows,aes(method,annual_cost)) + geom_col(fill=chart_tokens$accent,width=.55) + labs(title='Modeled annual operating cost',subtitle='Scenario estimates, not verified savings',x=NULL,y='Annual USD') + research_theme(13))
  }
  if(kind=='breakdown') return(ggplot(as_table(finance$activities),aes(reorder(activity,cost_per_fmea),cost_per_fmea)) + geom_col(fill=chart_tokens$accent) + coord_flip() + labs(title='Modeled cost by activity',x=NULL,y='USD per FMEA') + research_theme(13))
  if(kind=='sensitivity') return(ggplot(as_table(finance$sensitivity),aes(reorder(assumption,high-low),ymin=low,ymax=high)) + geom_linerange(linewidth=6,colour=chart_tokens$accent) + coord_flip() + labs(title='Scenario sensitivity',subtitle='Each assumption varied +/-20%; others held fixed',x=NULL,y='First-year net savings (USD)') + research_theme(13))
}
spending_plot <- function(finance) {
  rows <- as_table(finance$observed_spending)
  if(!nrow(rows) || !any(!is.na(rows$generation_timestamp)) || !any(!is.na(rows$known_billed_subtotal))) return(empty_plot('Observed cumulative API spending','No recorded invoices; actual spending is unknown'))
  rows <- rows[!is.na(rows$generation_timestamp),,drop=FALSE]
  ggplot(rows,aes(as.POSIXct(generation_timestamp,format='%Y-%m-%dT%H:%M:%S'),known_billed_subtotal)) +
    geom_step(colour=chart_tokens$accent,linewidth=.8) + labs(title='Known billed API subtotal',subtitle='Incomplete invoices: subtotal may be below total actual spending',x='Generation timestamp',y='Known invoice USD') + research_theme(13)
}
review_cost_plot <- function(finance) {
  rows <- as_table(finance$version_review_costs)
  if(!nrow(rows)) return(empty_plot('Modeled review cost by version','No selected evaluations; historical scenario remains separate'))
  ggplot(rows,aes(skill_version,modeled_mean_review_cost,fill=skill_version)) + geom_col(width=.6) + scale_fill_manual(values=palette) +
    labs(title='Modeled review cost by skill version',subtitle='Quality-linked review assumptions, not measured engineering labor',x=NULL,y='Modeled review USD per evaluated FMEA') + research_theme(13)
}
