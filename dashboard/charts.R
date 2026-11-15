# Dashboard presentation only. Python owns all counts, rates, intervals and scenarios.
# Academic constructors remain in plots.R; neither layer changes the snapshot.
if(!exists('chart_tokens')) source(file.path(if(file.exists('dashboard/theme.R')) 'dashboard' else '.', 'theme.R'))
esc <- function(x) htmltools::htmlEscape(as.character(x), attribute=TRUE)
fmt <- function(x, suffix='', money=FALSE) {
  if(is.null(x) || !length(x) || is.na(x[1]) || !is.finite(x[1])) return('Unknown')
  paste0(if(money) '$' else '',format(round(x[1],if(money) 0 else 1),big.mark=',',trim=TRUE),suffix)
}
chart_empty <- function(message='Awaiting independent evaluation',detail='Accepted judge evaluations will appear here.') {
  htmltools::div(class='chart-empty',htmltools::tags$p(message),htmltools::tags$small(detail))
}
chart_panel <- function(title,content,note=NULL) htmltools::tags$section(class='chart-panel',
  htmltools::tags$header(htmltools::tags$h2(title)),content,
  if(!is.null(note)) htmltools::tags$p(class='chart-note',note))
chart_details <- function(rows,label='View underlying data') {
  if(!nrow(rows)) return(NULL)
  header <- htmltools::tags$thead(htmltools::tags$tr(lapply(names(rows),htmltools::tags$th)))
  body <- htmltools::tags$tbody(lapply(seq_len(nrow(rows)),function(i) {
    cells <- lapply(rows,function(x) htmltools::tags$td(if(is.na(x[i])) 'Unknown' else as.character(x[i])))
    htmltools::tags$tr(cells)
  }))
  htmltools::tags$details(class='chart-details',htmltools::tags$summary(label),
    htmltools::div(class='table-responsive',htmltools::tags$table(header,body)))
}
svg_chart <- function(body,label,height=160) htmltools::HTML(paste0(
  '<svg class="native-chart" viewBox="0 0 400 ',height,'" role="img" aria-label="',esc(label),'">',
  '<title>',esc(label),'</title>',paste(body,collapse=''),'</svg>'))
mark <- function(shape,attrs,tip,action=NULL) paste0('<',shape,' ',attrs,' tabindex="0" class="chart-mark"',
  if(!is.null(action)) paste0(' data-run="',esc(action),'" role="button" aria-label="',esc(tip),'"') else '',
  '><title>',esc(tip),'</title></',shape,'>')
bar_rows <- function(labels,values,maximum,display=NULL,tips=labels,colors=NULL) {
  if(is.null(display)) display <- vapply(values,fmt,character(1))
  if(is.null(colors)) colors <- rep(chart_tokens$accent,length(values))
  htmltools::div(class='native-bars',lapply(seq_along(values),function(i) {
    htmltools::div(class='native-bar-row',title=tips[i],tabindex=0,
      htmltools::div(class='bar-label',labels[i]),htmltools::strong(display[i]),
      htmltools::div(class='bar-track',htmltools::div(class='bar-fill',style=paste0(
        'width:',if(is.finite(values[i]) && maximum>0) max(0,min(100,values[i]/maximum*100)) else 0,
        '%;background:',colors[i]))))
  }))
}
dashboard_activity <- function(d) {
  rows <- as_table(d$operations$generation_activity)
  registry <- as_table(d$registry)
  if(!nrow(rows)) return(chart_empty('No generation activity registered','Workflow success alone does not establish a generated FMEA.'))
  dates <- sort(unique(rows$date)); maxv <- max(1,rows$count); n <- length(dates)
  colors <- c(success=chart_tokens$accent,failed=chart_tokens$failure,running=chart_tokens$warning,queued=chart_tokens$muted,planned=chart_tokens$muted)
  body <- c('<line x1="10" x2="390" y1="130" y2="130" class="chart-grid"/>')
  # Display distinct statuses side by side, never sum workflow executions as FMEAs.
  for(i in seq_len(nrow(rows))) {
    day <- match(rows$date[i],dates); statuses <- unique(rows$generation_status); s <- match(rows$generation_status[i],statuses)
    w <- min(26,340/n/length(statuses)); x <- 20+(day-1)*360/n+(s-1)*w
    h <- rows$count[i]/maxv*100; color <- colors[rows$generation_status[i]]; if(is.na(color)) color <- chart_tokens$muted
    body <- c(body,mark('rect',sprintf('x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"',x,130-h,w-3,h,color),paste(rows$date[i],rows$generation_status[i],rows$count[i],'FMEA attempts')))
  }
  body <- c(body,sprintf('<text x="10" y="151">%s</text><text x="390" y="151" text-anchor="end">%s</text>',esc(dates[1]),esc(tail(dates,1))))
  # A pending mark represents one actual successful receipt, not a new attempt.
  pending <- if(nrow(registry)) registry[registry$generation_status=='success' & registry$evaluation_status!='evaluated',,drop=FALSE] else registry
  if(nrow(pending) && 'generation_timestamp' %in% names(pending)) for(i in seq_len(nrow(pending))) {
    day <- match(substr(pending$generation_timestamp[i],1,10),dates)
    if(!is.na(day)) body <- c(body,mark('circle',sprintf('cx="%f" cy="14" r="3" fill="%s"',20+(day-1)*360/n+(i%%7)*5,chart_tokens$warning),
      paste(pending$run_id[i],'awaiting independent evaluation')))
  }
  htmltools::tagList(htmltools::div(class='chart-key',htmltools::span('Successful',class='key-success'),htmltools::span('Failed',class='key-failed'),htmltools::span('Awaiting judge (dots)',class='key-pending')),
    svg_chart(body,'Registered FMEA generation attempts by date and status'),
    htmltools::tags$p(class='chart-note',paste(fmt(d$operations$awaiting_judge),'awaiting independent evaluation. Generation receipts, not workflow execution totals.')),
    chart_details(rows,'Activity counts and source dates'))
}
dashboard_runs <- function(d,runs=as_table(d$runs),scatter=FALSE) {
  if(!nrow(runs)) return(chart_empty())
  if(scatter) runs <- runs[is.finite(runs$generated_rows),,drop=FALSE]
  if(!nrow(runs)) return(chart_empty('Generated row counts unavailable'))
  htmltools::tagList(lapply(split(runs,runs$system),function(r) {
    x <- if(scatter) r$generated_rows else seq_len(nrow(r)); span <- range(c(0,x),na.rm=TRUE); denom <- max(1,diff(span))
    body <- c('<line x1="12" x2="388" y1="106" y2="106" class="chart-target"/>',
      '<text x="12" y="17">100%</text><text x="388" y="102" text-anchor="end">20% target</text><text x="12" y="143">0%</text>')
    for(i in seq_len(nrow(r))) {
      tip <- paste(r$run_id[i],r$skill_version[i],fmt(r$missed_percentage[i],'% missed'),if(scatter) paste(r$generated_rows[i],'generated rows') else '')
      body <- c(body,mark('circle',sprintf('cx="%.2f" cy="%.2f" r="5" fill="%s"',30+350*(x[i]-span[1])/denom,130-r$missed_percentage[i]*1.2,palette[[r$skill_version[i]]]),tip,r$run_id[i]))
    }
    if(scatter) body <- c(body,sprintf('<text x="388" y="153" text-anchor="end">%s generated rows</text>',esc(max(x))))
    htmltools::div(class='run-system',htmltools::tags$h3(paste('System',r$system[1])),
      svg_chart(body,paste('System',r$system[1],nrow(r),'evaluated FMEAs; missed reference opportunities percent')))
  }),htmltools::div(class='chart-key',lapply(unique(runs$skill_version),function(v) htmltools::span(style=paste0('color:',palette[[v]]),v))),
    htmltools::tags$p(class='chart-note','Select a point for run details. Values are accepted evaluations only.'),
    chart_details(runs[,intersect(c('run_id','system','skill_version','missed_percentage','generated_rows'),names(runs)),drop=FALSE],'Inspect evaluated runs'))
}
dashboard_versions <- function(d) {
  rows <- as_table(d$per_version)
  htmltools::tagList(lapply(c('v2.0','v3.0','v3.0-audit','v4.0'),function(v) {
    r <- if(nrow(rows)) rows[rows$skill_version==v,,drop=FALSE] else rows
    if(!nrow(r)) return(htmltools::div(class='version-line',htmltools::strong(v),htmltools::span('Awaiting independent evaluation')))
    value <- r$system_weighted_mean[1]
    interval <- if(!is.na(r$ci_low[1]) && !is.na(r$ci_high[1])) paste('95% CI',fmt(r$ci_low[1]),'to',fmt(r$ci_high[1]),'%') else '95% CI unavailable'
    htmltools::div(class='version-result',bar_rows(v,value,100,fmt(value,'%'),paste(v,interval),palette[[v]]),
      htmltools::tags$small(paste('n =',r$runs[1],'evaluated FMEAs \u00b7',interval)))
  }),htmltools::tags$p(class='chart-note','Equal-system mean missed percentage. Target below 20%. Intervals use the complete validated cohort.'),
    htmltools::tags$details(class='chart-details',htmltools::tags$summary('Historical V2 baseline'),
      htmltools::tags$p(paste(fmt(d$baseline$pooled_missed_percentage_reported,'%'),'pooled missed;',d$baseline$total_runs,'reported FMEAs. Aggregate only; no run observations or inferred interval.'))))
}
dashboard_pareto <- function(d) {
  rows <- as_table(d$pareto); historical <- !nrow(rows)
  if(historical) rows <- data.frame(miss_category=names(d$baseline$miss_categories),count=as.numeric(unlist(d$baseline$miss_categories)),percentage=as.numeric(unlist(d$baseline$miss_category_percentages)),skill_version='Historical V2 report')
  htmltools::tagList(lapply(split(rows,rows$skill_version),function(r) {
    r <- r[order(-r$count),,drop=FALSE]
    htmltools::div(htmltools::tags$h3(r$skill_version[1]),bar_rows(r$miss_category,r$count,max(1,r$count),
      paste0(r$count,' \u00b7 ',vapply(r$percentage,fmt,character(1),suffix='%'))))
  }),htmltools::tags$p(class='chart-note',if(historical) 'Report-derived category totals. Evaluated version comparisons pending.' else 'Validated classifications. Unclassified cases remain visible.'),chart_details(rows,'Category counts and percentages'))
}
dashboard_agreement <- function(d) {
  labels <- c(cause_correctness='Cause \u00b7 agreement',end_effect_correctness='End effect \u00b7 agreement',severity_within_one='Severity \u00b7 within \u00b11',occurrence_within_one='Occurrence \u00b7 within \u00b11',detection_within_one='Detection \u00b7 within \u00b11',rpn_within_25_percent='RPN \u00b7 within 25%')
  rows <- as_table(d$field_accuracy); historical <- !nrow(rows) || !any(!is.na(rows$accuracy_percentage))
  if(historical) rows <- data.frame(field=names(d$baseline$conditional_quality_reported),accuracy_percentage=100*as.numeric(unlist(d$baseline$conditional_quality_reported)),skill_version='Historical V2 report')
  rows <- rows[!is.na(rows$accuracy_percentage),,drop=FALSE]
  if(!nrow(rows)) return(chart_empty())
  htmltools::tagList(lapply(split(rows,rows$skill_version),function(r) {
    l <- unname(labels[r$field]); l[is.na(l)] <- r$field[is.na(l)]
    htmltools::div(htmltools::tags$h3(r$skill_version[1]),bar_rows(l,r$accuracy_percentage,100,vapply(r$accuracy_percentage,fmt,character(1),suffix='%')))
  }),htmltools::tags$p(class='chart-note',if(historical) 'Report-derived conditional agreement. Matched-item denominators unavailable.' else 'Conditional agreement among matched reference items; tolerances differ by field.'),chart_details(rows,'Agreement values and denominators'))
}
dashboard_finance <- function(f,kind) {
  if(is.null(f)) return(chart_empty('Scenario unavailable','Check Python dependencies and assumptions.'))
  if(kind=='comparison') return(bar_rows(c('Manual','AI-assisted'),c(f$modeled$manual_annual_cost,f$modeled$ai_annual_operating_cost),max(1,f$modeled$manual_annual_cost,f$modeled$ai_annual_operating_cost),c(fmt(f$modeled$manual_annual_cost,money=TRUE),fmt(f$modeled$ai_annual_operating_cost,money=TRUE)),colors=c(chart_tokens$muted,chart_tokens$accent)))
  if(kind=='breakdown') {
    r <- as_table(f$activities); return(htmltools::tagList(bar_rows(r$activity,r$cost_per_fmea,max(1,r$cost_per_fmea),vapply(r$cost_per_fmea,fmt,character(1),money=TRUE)),chart_details(r)))
  }
  if(kind=='simulation') {
    r <- as_table(f$simulation$histogram); if(!nrow(r)) return(chart_empty('Simulation unavailable'))
    lo <- min(c(0,r$midpoint)); hi <- max(c(1,r$midpoint)); sx <- function(v) 12+376*(v-lo)/(hi-lo)
    body <- c('<line x1="12" x2="388" y1="145" y2="145" class="chart-grid"/>')
    for(i in seq_len(nrow(r))) {h <- r$count[i]/max(1,r$count)*115; body <- c(body,mark('rect',sprintf('x="%.2f" y="%.2f" width="7" height="%.2f" fill="%s"',sx(r$midpoint[i])-3.5,145-h,h,chart_tokens$accent),paste(fmt(r$midpoint[i],money=TRUE),r$count[i],'simulation draws')))}
    body <- c(body,sprintf('<line x1="%f" x2="%f" y1="20" y2="145" class="chart-target"/>',sx(0),sx(0)),sprintf('<text x="12" y="168">%s</text><text x="388" y="168" text-anchor="end">%s</text>',esc(fmt(lo,money=TRUE)),esc(fmt(hi,money=TRUE))))
    return(htmltools::tagList(svg_chart(body,'Modeled annual net savings in USD; negative outcomes retained; dashed line is zero',180),htmltools::tags$p(class='chart-note',paste('Median',fmt(f$simulation$median_annual_net_savings,money=TRUE),'\u00b7 95% simulation interval',paste(vapply(f$simulation$interval95_annual_usd,fmt,character(1),money=TRUE),collapse=' to '))),chart_details(r,'Simulation bins (not observed savings)')))
  }
  if(kind=='sensitivity') {
    r <- as_table(f$sensitivity); lo <- min(c(0,r$low)); hi <- max(c(1,r$high)); span <- hi-lo
    labels <- c(labor_rate='Engineering labor rate',manual_hours='Manual drafting time',missed_reconstruction_minutes='Missed-item reconstruction',matched_review_minutes='Matched-item review',annual_volume='Annual FMEA volume')
    return(htmltools::tagList(lapply(seq_len(nrow(r)),function(i) htmltools::div(class='sensitivity-row',
      htmltools::div(class='range-label',unname(labels[r$assumption[i]])),
      htmltools::div(class='range-track',htmltools::div(class='range-fill',style=sprintf('left:%f%%;width:%f%%',(r$low[i]-lo)/span*100,(r$high[i]-r$low[i])/span*100))),
      htmltools::tags$small(paste(fmt(r$low[i],money=TRUE),'to',fmt(r$high[i],money=TRUE))))),
      htmltools::tags$p(class='chart-note','First-year net savings; each assumption varied \u00b120%, others held fixed. Shared USD scale.'),chart_details(r)))
  }
  if(kind=='spending') {
    r <- as_table(f$observed_spending)
    if(!nrow(r) || !any(!is.na(r$known_billed_subtotal))) return(chart_empty('Actual spending unknown','No recorded invoices. Missing billed costs are not zero.'))
    r <- r[!is.na(r$known_billed_subtotal) & !is.na(r$generation_timestamp),,drop=FALSE]
    if(!nrow(r)) return(chart_empty('Invoice timestamps unavailable'))
    times <- as.numeric(as.POSIXct(r$generation_timestamp,format='%Y-%m-%dT%H:%M:%S',tz='UTC')); minx <- min(times); span <- max(1,max(times)-minx)
    xx <- 12+376*(times-minx)/span; yy <- 130-r$known_billed_subtotal/max(1,r$known_billed_subtotal)*110
    points <- paste(sprintf('%f,%f',xx,yy),collapse=' ')
    body <- c(paste0('<polyline points="',points,'" fill="none" stroke="',chart_tokens$accent,'"/>'))
    for(i in seq_len(nrow(r))) body <- c(body,mark('circle',sprintf('cx="%f" cy="%f" r="4" fill="%s"',xx[i],yy[i],chart_tokens$accent),paste(r$generation_timestamp[i],fmt(r$known_billed_subtotal[i],money=TRUE),'known billed subtotal')))
    return(htmltools::tagList(svg_chart(body,'Known billed API subtotal over time; invoices may be incomplete'),htmltools::tags$p(class='chart-note','Known billed subtotal, not necessarily complete actual spending.'),chart_details(r)))
  }
  if(kind=='versions') {
    r <- as_table(f$version_review_costs); if(!nrow(r)) return(chart_empty('Review-cost comparison pending','No accepted version-level evaluations.'))
    return(bar_rows(r$skill_version,r$modeled_mean_review_cost,max(1,r$modeled_mean_review_cost),vapply(r$modeled_mean_review_cost,fmt,character(1),money=TRUE)))
  }
  stop('Unknown dashboard financial chart')
}
