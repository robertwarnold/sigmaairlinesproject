# Presentation figures only display Python-computed quantities and intervals.
library(ggplot2)
palette <- c('v2.0' = '#59646c', 'v3.0' = '#967126', 'v4.0' = '#145e63')
research_theme <- function(size = 15) {
  theme_minimal(base_size = size) + theme(
    plot.background = element_rect(fill = '#f7f5ef', colour = NA),
    panel.background = element_rect(fill = '#f7f5ef', colour = NA),
    panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(),
    plot.title = element_text(face = 'bold', colour = '#172b36'),
    plot.subtitle = element_text(colour = '#384e5a'), legend.position = 'bottom',
    axis.text = element_text(colour = '#263e49'))
}
coverage_plot <- function(data, selected = NULL) {
  runs <- if (is.null(selected)) as_table(data$runs) else selected
  if (!nrow(runs) && !is.null(selected)) return(ggplot() + annotate('text',x=0,y=0,label='No evaluated observations match the filters',size=6) + theme_void())
  if (!nrow(runs)) {
    # A single aggregate report point is never portrayed as run-level evidence.
    return(ggplot(data.frame(version = 'V2 report aggregate', missed = data$baseline$pooled_missed_percentage_reported), aes(version, missed)) +
      geom_hline(yintercept = 20, linetype = 'dashed', colour = '#966021') +
      geom_point(size = 5, colour = palette[['v2.0']]) +
      annotate('text', x = 1, y = 65, label = 'V3 and V4: Pending Evaluation\nRun-level confidence intervals unavailable', size = 5) +
      scale_y_continuous(limits = c(0,100)) + labs(title = 'Failure-mode coverage comparison', subtitle = 'Report-derived V2 pooled rate; no evaluated V4 observations', x = NULL, y = 'Missed failure modes (%)', caption = 'Dashed line: V4 target below 20%. Aggregate point has no inferred CI.') + research_theme())
  }
  means <- as_table(data$per_system)
  if (nrow(means)) means <- means[paste(means$skill_version,means$system) %in% paste(runs$skill_version,runs$system),,drop=FALSE]
  p <- ggplot(runs, aes(skill_version, missed_percentage, colour = skill_version)) +
    geom_hline(yintercept = 20, linetype = 'dashed', colour = '#966021') +
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
  ggplot(rows, aes(label, count)) + geom_col(fill = '#145e63', width = .65) +
    geom_line(aes(y = cumulative_percentage * max_count/100, group = skill_version), colour = '#966021', linewidth = .8) +
    geom_point(aes(y = cumulative_percentage * max_count/100), colour = '#966021', size = 2) +
    facet_wrap(~skill_version,scales = 'free_x') + scale_y_continuous(sec.axis = sec_axis(~ . * 100/max_count, name = 'Cumulative missed modes (%)')) +
    labs(title = 'Pareto: where failure modes were missed', subtitle = if (reported) 'V2 report-derived category totals; V3/V4 pending' else 'Validated item-level classifications; unclassified cases remain visible',
         x = NULL, y = 'Missed opportunities', caption = 'Categories are mutually exclusive. Counts and percentages come from Python.') +
    research_theme(13) + theme(axis.text.x = element_text(angle = 18, hjust = 1))
}
overall_plot <- function(data) {
  rows <- as_table(data$per_version)
  if (!nrow(rows)) return(coverage_plot(data))
  ggplot(rows,aes(skill_version, system_weighted_mean, colour = skill_version)) +
    geom_hline(yintercept = 20,linetype = 'dashed',colour = '#966021') + geom_point(size = 4) +
    geom_errorbar(aes(ymin = ci_low,ymax = ci_high),width = .12,na.rm = TRUE) +
    scale_colour_manual(values = palette) + labs(title = 'Overall missed percentage', subtitle = 'Equal-system mean and system-stratified 95% interval; run mean shown separately', x = NULL,y = 'Missed (%)') + research_theme()
}
