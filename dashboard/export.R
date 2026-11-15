# Usage: Rscript dashboard/export.R snapshot.json output-directory
source(if (file.exists('dashboard/bootstrap.R')) 'dashboard/bootstrap.R' else 'bootstrap.R')
source(file.path(dashboard_dir,'data.R')); source(file.path(dashboard_dir,'plots.R')); source(file.path(dashboard_dir,'poster.R'))
args <- commandArgs(trailingOnly=TRUE)
if (length(args)!=2) stop('Supply sanitized snapshot JSON and export directory')
data <- read_snapshot(args[1]); dir.create(args[2],recursive=TRUE,showWarnings=FALSE)
for (name in c('coverage','pareto')) {
  plot <- if (name=='coverage') coverage_plot(data) else pareto_plot(data)
  ggplot2::ggsave(file.path(args[2],paste0(name,'.png')),plot,width=13,height=6.5,dpi=300)
  ggplot2::ggsave(file.path(args[2],paste0(name,'.pdf')),plot,width=13,height=6.5)
}
poster_export(data,file.path(args[2],'poster.pdf'))
