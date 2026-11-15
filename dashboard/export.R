# Usage: Rscript dashboard/export.R snapshot.json output-directory
source(if (file.exists('dashboard/bootstrap.R')) 'dashboard/bootstrap.R' else 'bootstrap.R')
source(file.path(dashboard_dir,'data.R')); source(file.path(dashboard_dir,'plots.R')); source(file.path(dashboard_dir,'poster.R'))
args <- commandArgs(trailingOnly=TRUE)
if (length(args)!=2) stop('Supply sanitized snapshot JSON and export directory')
data <- read_snapshot(args[1]); dir.create(args[2],recursive=TRUE,showWarnings=FALSE)
plots <- list(coverage=coverage_plot(data),pareto=pareto_plot(data),version_comparison=overall_plot(data),field_accuracy=field_accuracy_plot(data),generation_activity=activity_plot(data),quality_completeness=completeness_plot(data))
if(!is.null(data$financial)) {
  plots$financial_monte_carlo <- financial_plot(data$financial,'simulation')
  plots$financial_cost <- financial_plot(data$financial,'comparison')
  plots$financial_breakdown <- financial_plot(data$financial,'breakdown')
  plots$financial_sensitivity <- financial_plot(data$financial,'sensitivity')
  plots$financial_spending <- spending_plot(data$financial)
  plots$financial_versions <- review_cost_plot(data$financial)
}
for (name in names(plots)) {
  plot <- plots[[name]]
  ggplot2::ggsave(file.path(args[2],paste0(name,'.png')),plot,width=13,height=6.5,dpi=300)
  ggplot2::ggsave(file.path(args[2],paste0(name,'.pdf')),plot,width=13,height=6.5)
}
poster_export(data,file.path(args[2],'poster.pdf'))
