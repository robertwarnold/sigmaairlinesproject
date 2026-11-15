# Grid composition avoids browser/LaTeX dependencies and exports a true 16:9 PDF.
poster_export <- function(data, path) {
  grDevices::pdf(path, width = 24, height = 13.5, family = 'Helvetica', bg = '#f7f5ef')
  on.exit(grDevices::dev.off(), add = TRUE)
  grid::grid.newpage()
  grid::grid.rect(gp = grid::gpar(fill = '#f7f5ef', col = NA))
  text <- function(label,x,y,size=18,col='#172b36',face='plain',just='left') grid::grid.text(label,x,y,just=just,gp=grid::gpar(fontsize=size,col=col,fontface=face))
  text('SIGMA AIRLINES  /  SYSEN 5300',.035,.95,18,'#145e63','bold')
  text('Can structured engineering coverage reduce missed failure modes?',.035,.89,32,face='bold')
  v4 <- as_table(data$per_version); if (nrow(v4)) v4 <- v4[v4$skill_version=='v4.0',,drop=FALSE]
  v4_label <- if (nrow(v4)) sprintf('V4 run mean: %.1f%%',v4$mean_run_missed_percentage[1]) else 'V4: Pending Evaluation'
  text(paste0('V2 report pooled: ',data$baseline$pooled_missed_percentage_reported,'%  |  ',v4_label,'  |  ',data$research_status),.035,.83,19)
  print(coverage_plot(data),vp=grid::viewport(x=.27,y=.55,width=.49,height=.47))
  print(pareto_plot(data),vp=grid::viewport(x=.76,y=.55,width=.45,height=.47))
  text('DATA',.035,.275,17,'#145e63','bold')
  text(sprintf('V2 report: %d runs; %d opportunities; %d misses.\nV4 plan: five systems, four independent generations each.\nOnly validated evaluations enter comparative analysis.',data$baseline$total_runs,data$baseline$opportunities,data$baseline$missed),.035,.22,15)
  text('METHOD',.365,.275,17,'#145e63','bold')
  text('DMAIC Improve / Control; input-bound coverage audit.\nUnchanged independent judge and human review.\nAdditive ANOVA; system-stratified bootstrap 95% CI.',.365,.22,15)
  text('DISCUSSION / IMPLICATIONS',.70,.275,17,'#145e63','bold')
  text('Higher row volume does not establish engineering quality.\nBaseline aggregates cannot support run-level significance.\nNo efficacy claim before comparable V4 evaluation.',.70,.22,15)
  improvement <- data$statistics$confidence_intervals$improvement
  ci_label <- if (is.null(improvement)) 'Improvement and 95% CI: Pending comparable run-level data' else sprintf('Improvement %.1f pp (95%% CI %.1f to %.1f)', improvement$percentage_points, improvement$ci_low, improvement$ci_high)
  text(ci_label,.035,.12,18,face='bold')
  criteria <- data$statistics$criteria
  text(paste(paste(names(criteria),unlist(criteria),sep=': '),collapse='  |  '),.035,.075,10)
  text(paste('Snapshot',substr(data$data_version,1,12),'|',data$last_updated,'| AI-assisted presentation draft: students must verify and rewrite submitted prose.'),.035,.035,10)
}
