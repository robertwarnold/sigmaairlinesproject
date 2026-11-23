# Presentation of Python-selected analytics; no research calculations in the frontend.
engineering_matrix_chart <- function(matrix) {
  body <- character()
  for(s in 1:10) for(o in 1:10) {
    value <- if(nrow(matrix)) matrix$count[matrix$severity==s & matrix$occurrence==o] else numeric()
    n <- if(length(value)) value[1] else 0
    body <- c(body,paste0('<rect x="',35+(o-1)*33,'" y="',15+(10-s)*20,'" width="29" height="17" fill="',if(n) chart_tokens$accent else chart_tokens$raised,'" data-engineering-cell="',s,',',o,'" tabindex="0" role="button" aria-label="Severity ',s,', occurrence ',o,': ',n,' rows"><title>S ',s,' / O ',o,' / ',n,' rows</title></rect>'))
    if(n) body <- c(body,paste0('<text x="',49+(o-1)*33,'" y="',27+(10-s)*20,'" text-anchor="middle" style="fill:#fff">',n,'</text>'))
  }
  for(i in 1:10) body <- c(body,paste0('<text x="',49+(i-1)*33,'" y="230" text-anchor="middle">',i,'</text><text x="20" y="',27+(10-i)*20,'">',i,'</text>'))
  svg_chart(c(body,'<text x="35" y="250">Occurrence \u2192 / severity 10 to 1 (top to bottom)</text>'),
    'Severity versus occurrence, existing 1-10 scales. Row counts only; not a formal risk acceptance matrix.',265)
}
engineering_analytics_server <- function(input,output,session,allowed,state,filtered,command,folder,focus_ids,research,identity_mapping=list()) {
  selection <- debounce(reactive(filtered()$record_id),250)
  analytics <- reactive({
    if(!allowed()||is.null(state()$summary)) return(NULL)
    ids <- selection(); if(is.null(ids)) ids <- character()
    path <- file.path(folder,'analytics-selection.json'); target <- file.path(folder,'analytics.json')
    jsonlite::write_json(as.list(ids),path,auto_unbox=TRUE)
    command('analytics',c('--selection',shQuote(path),'--output',shQuote(target)))
    jsonlite::fromJSON(target,simplifyDataFrame=TRUE)
  })
  pending <- function() chart_empty('No imported FMEA records',if(!allowed()) 'Private row analytics are available only in the opt-in local workstation.' else 'Explicitly import a generated V4 bundle, or adjust the filters.')
  output$analytics_context <- renderUI({
    r <- filtered(); meta <- as_table(state()$comparisons)
    synthetic <- nrow(meta)&&any(grepl('synthetic|demo',meta$data_origin,ignore.case=TRUE))
    extra <- !is.null(focus_ids()) || (!is.null(input$eng_search)&&nzchar(input$eng_search)) ||
      (!is.null(input$eng_severity)&&input$eng_severity!='All') || (!is.null(input$eng_occurrence)&&input$eng_occurrence!='All')
    span(if(synthetic) strong('SYNTHETIC TEST DATA \u00b7 NOT RESEARCH FINDINGS \u00b7 ') else '',
      if(!allowed()) paste('Sanitized operational dataset / active skill:',if(is.null(input$g_skill)||input$g_skill=='All') 'all registered versions' else input$g_skill,'/ no private row access') else if(nrow(r)) paste('Input dataset:',paste(unique(r$dataset_version),collapse=', '),'\u00b7 Skill:',paste(unique(r$skill_version),collapse=', ')) else 'Private workstation \u00b7 no matching imported rows',
      if(allowed()&&!is.null(state()$updated_at)) paste('/ Private refreshed:',substr(state()$updated_at,1,19),'UTC'),
      if(extra) tagList(' / Record filters active ',tags$button(id='clear_record_context',type='button',class='btn','Clear record filters')))
  })
  output$analytics_health <- renderUI({
    a <- analytics(); k <- a$kpis
    card <- function(label,value,detail,key) tags$button(type='button',class='health-card',`data-attention`=key,title=detail,
      span(class='metric-label',label),strong(value),tags$small(detail))
    value <- function(x,suffix='') if(is.null(x)) '\u2014' else paste0(format(round(x,1),trim=TRUE,big.mark=','),suffix)
    div(class='health-grid',card('Total failure modes',value(k$total),'Selected imported rows / replicas kept separate','all'),
      card('High severity',value(k$high_severity),'S \u2265 9 / existing 1\u201310 scoring policy','high'),
      card('Average RPN',value(k$average_rpn),paste(if(is.null(k$valid_rpn_count)) 'No' else k$valid_rpn_count,'valid S \u00d7 O \u00d7 D records'),'valid_rpn'),
      card('Evidence coverage',value(k$cited_evidence_percentage,'%'),'Citation present / not verified support','evidence'),
      card('Validation pass rate',value(k$validation_percentage,'%'),'Current structural checks / selected rows','validation'),
      card('Engineering reviewed',value(k$reviewed),'Approved or rejected / self-asserted reviewer','reviewed'))
  })
  output$analytics_attention <- renderUI({
    a <- analytics()
    if(is.null(a)) return(p('Generated receipts are available below. Import private V4 records to inspect technical findings; independent evaluation remains separate.'))
    findings <- as_table(a$attention)
    if(!nrow(findings)) return(p(if(a$selection_count==0) 'No matching records. Reset filters or import a generated V4 bundle.' else 'No automatic attention flags in this selection. Engineering verification is still required.'))
    tags$ul(lapply(seq_len(nrow(findings)),function(i) tags$li(tags$button(type='button',`data-attention`=findings$key[i],
      strong(paste0(findings$count[i],' ')),findings$label[i]))))
  })
  observeEvent(input$analytics_attention_pick,{
    a <- analytics(); if(is.null(a)) return()
    r <- filtered(); key <- input$analytics_attention_pick
    ids <- switch(key,all=NULL,high=r$record_id[!is.na(r$severity)&r$severity>=9],
      ratings=r$record_id[is.na(r$RPN)],valid_rpn=r$record_id[!is.na(r$RPN)],evidence=r$record_id[r$evidence_status=='missing'],
      validation=r$record_id[r$structural_status!='PASS'],reviewed=r$record_id[r$review_status %in% c('APPROVED','REJECTED')],NULL)
    if(key=='duplicates') {
      f <- as_table(a$attention); if(nrow(f)) ids <- unlist(f$record_ids[f$key==key],use.names=FALSE)
    }
    focus_ids(ids); updateNumericInput(session,'eng_page',value=1)
  })
  output$analytics_subsystems <- renderUI({
    a <- analytics(); d <- as_table(a$subsystems); if(!nrow(d)) return(pending())
    bands <- c('High (9-10)','Other valid (1-8)','Unrated'); colors <- c('#d77982','#589bc8','#aab5bf'); groups <- unique(d$subsystem)
    tagList(div(class='chart-legend',lapply(seq_along(bands),function(i) span(style=paste0('color:',colors[i]),bands[i]))),
      lapply(groups,function(g) {x<-d[d$subsystem==g,,drop=FALSE]; div(class='subsystem-stack',strong(g),div(class='stack-track',lapply(seq_len(nrow(x)),function(i)
        span(style=paste0('width:',x$width_percentage[i],'%;background:',colors[match(x$severity_band[i],bands)]),title=paste(g,x$severity_band[i],x$count[i],'rows'),x$count[i]))))}),
      chart_details(d,'Subsystem and severity counts'))
  })
  output$analytics_matrix <- renderUI({a<-analytics(); if(is.null(a)||!a$selection_count) return(pending());engineering_matrix_chart(as_table(a$matrix))})
  output$analytics_rpn <- renderUI({a<-analytics();if(is.null(a)||!a$selection_count)return(pending());tagList(engineering_rpn_chart(as_table(a$rpn_bins)),p(class='chart-note',paste(a$kpis$valid_rpn_count,'valid ratings; other rows excluded.')),chart_details(as_table(a$rpn_bins),'Bin definitions and counts'))})
  output$analytics_causes <- renderUI({
    a<-analytics();d<-as_table(a$cause_categories);if(!nrow(d))return(pending())
    if(all(d$category=='Not categorized')) return(chart_empty('Cause taxonomy unavailable','Cause text exists, but no reviewed cause categories were supplied. Failure-mode categories are not cause categories.'))
    bar_rows(d$category,d$count,max(1,d$count))
  })
  output$analytics_priority <- renderUI({
    a<-analytics();d<-as_table(a$priorities);if(!nrow(d))return(pending())
    key<-if(identical(input$priority_order,'RPN')) 'RPN' else 'severity'
    d<-d[order(d[[key]],decreasing=TRUE,na.last=TRUE),,drop=FALSE]
    # Pin high severity ahead of the remaining ranking, even when ordering by RPN.
    d<-rbind(d[which(!is.na(d$severity)&d$severity>=9),,drop=FALSE],d[which(is.na(d$severity)|d$severity<9),,drop=FALSE]);d<-head(d,5)
    tagList(lapply(seq_len(nrow(d)),function(i) div(`data-engineering-record`=d$record_id[i],role='button',tabindex=0,
      bar_rows(substr(d$label[i],1,65),ifelse(is.na(d[[key]][i]),0,d[[key]][i]),max(c(1,d[[key]]),na.rm=TRUE),
      display=ifelse(is.na(d[[key]][i]),'Unknown',d[[key]][i]),tips=paste(d$label[i],d$run_id[i],'S',d$severity[i],'RPN',d$RPN[i])))),
      p(class='chart-note','High-severity items pinned first. This is a review priority, not a risk acceptance decision.'),
      chart_details(d,'Priority records and identifiers'))
  })
  output$analytics_actions <- renderUI({a<-analytics();d<-as_table(a$actions);if(!nrow(d))return(chart_empty('Action tracking unavailable','Recommended actions do not establish status, due dates or completion.'));bar_rows(d$status,d$count,max(1,d$count))})
  output$analytics_evidence <- renderUI({a<-analytics();d<-as_table(a$evidence);if(!nrow(d))return(pending());tagList(bar_rows(d$status,d$count,max(1,d$count),tips=paste(d$status,d$count,'of',a$selection_count,'rows')),p(class='chart-note','No unsupported-claim classification is inferred. Human-approved inference is not source verification.'))})
  output$analytics_versions <- renderUI({
    a<-analytics();d<-as_table(a$runs);if(!nrow(d))return(chart_empty('Pending evaluated skill observations','V4.1 and V4.2 name dashboard revisions. They are not fabricated FMEA skill treatments.'))
    tagList(lapply(split(d,d$comparison_key),function(group) tagList(p(class='chart-note',paste('Compatible input/policy group',substr(group$comparison_key[1],1,10))),
      bar_rows(paste(group$skill_version,substr(group$run_id,1,35)),group$validation_percentage,100,display=paste0(round(group$validation_percentage,1),'%')),
      chart_details(group[,intersect(c('run_id','skill_version','generator_model','selected_rows','reviewed_rows','approved_rows','acceptance_percentage','validation_percentage'),names(group)),drop=FALSE],'Run denominators and engineering acceptance'))),
      p(class='chart-note','No reference recall or unsupported-assertion rate without independent evaluation. Different condition groups are not pooled.'))
  })
  output$analytics_duration <- renderUI({
    a<-analytics();d<-as_table(a$runs)
    if(!nrow(d)&&!is.null(research)) d<-filter_generation_rows(as_table(research()$registry),list(run=input$g_run,system=input$g_system,model=input$g_model,skill=input$g_skill,dates=input$g_dates,subsystem=input$g_subsystem,review=input$g_review))
    timing<-intersect(c('generation_seconds','generation_duration','duration'),names(d))
    if(!nrow(d)||!length(timing))return(chart_empty('Generation timing unavailable','No reliable per-attempt duration in this filtered dataset. Missing costs remain unknown.'))
    if(is.list(d[[timing[1]]])) d[[timing[1]]]<-vapply(d[[timing[1]]],function(x)if(is.numeric(x)&&length(x)==1&&is.finite(x))x else NA_real_,numeric(1))
    d<-d[which(!is.na(d[[timing[1]]])&d[[timing[1]]]>=0),,drop=FALSE]
    if('generation_status' %in% names(d))d<-d[d$generation_status=='success',,drop=FALSE]
    if(!nrow(d))return(chart_empty('No successful timed generations','Failed attempts are excluded from successful generation duration.'))
    d<-d[order(d$skill_version,d$system,d[[timing[1]]],na.last=TRUE),,drop=FALSE]
    labels <- experiment_labels(d,identity_mapping)
    tagList(bar_rows(paste(labels,d$skill_version,sep=' / '),d[[timing[1]]],max(1,d[[timing[1]]]),
      display=paste(round(d[[timing[1]]],1),'s'),tips=d$run_id),
      p(class='chart-note','Recorded generator duration per successful run. Labor and queue time require separate observations.'))
  })
  output$analytics_agreement <- renderUI({a<-analytics();d<-as_table(a$agreement);if(!nrow(d)||all(is.na(d$within_one_percentage)))return(chart_empty('Insufficient reviewed rating pairs','At least two explicit human corrections per rating are required. Approval without a rating correction is not an independent rating observation.'));tagList(bar_rows(d$rating,ifelse(is.na(d$within_one_percentage),0,d$within_one_percentage),100,display=ifelse(is.na(d$within_one_percentage),'Pending',paste0(round(d$within_one_percentage,1),'%')),tips=paste(d$rating,'n =',d$n)),chart_details(d,'Agreement denominators'))})
  output$analytics_trends <- renderUI({
    a<-analytics();d<-as_table(a$runs);if(!nrow(d))return(pending())
    tagList(lapply(seq_len(min(nrow(d),8)),function(i)tagList(p(class='chart-note',substr(d$run_id[i],1,60)),
      bar_rows(c('Duplicate','Structural failure'),c(d$duplicate_percentage[i],d$validation_failure_percentage[i]),100,
        display=paste0(round(c(d$duplicate_percentage[i],d$validation_failure_percentage[i]),1),'%'),colors=c('#8d78b4','#d77982')))),
      chart_details(data.frame(Run=d$run_id,Duplicate_percent=d$duplicate_percentage,Validation_failure_percent=d$validation_failure_percentage,Rows=d$selected_rows),'All run denominators'))
  })
  output$analytics_experiments <- renderUI({
    a<-analytics();d<-as_table(a$runs)
    if(!nrow(d))return(chart_empty('No imported engineering experiments','The GitHub generation registry remains available below; it does not supply private failure-mode rows.'))
    fields<-c(run_id='Run ID',skill_version='Skill',generator_model='Model',dataset_version='Dataset',selected_rows='Rows',validation_percentage='Structural pass (%)',generation_seconds='Seconds',generation_timestamp='Date (UTC)')
    names_present<-intersect(names(fields),names(d));d<-d[,names_present,drop=FALSE]
    if('generation_timestamp' %in% names(d)) d$generation_timestamp<-substr(d$generation_timestamp,1,10)
    names(d)<-unname(fields[names_present])
    table<-chart_details(d,'Selected engineering runs');table$attribs$open<-TRUE;table
  })
  output$analytics_judge <- renderUI({
    if(is.null(research))return(chart_empty('Awaiting independent evaluation'))
    d<-filter_generation_rows(as_table(research()$runs),list(run=input$g_run,system=input$g_system,model=input$g_model,skill=input$g_skill,dates=input$g_dates,subsystem=input$g_subsystem,review=input$g_review))
    if(!nrow(d))return(chart_empty('Awaiting independent evaluation','Historical V2 aggregates remain separate in research context. No invented V4 observations.'))
    chart_details(d[,intersect(c('run_id','skill_version','system','missed_percentage','dpmo'),names(d)),drop=FALSE],'Accepted independent observations')
  })
  observeEvent(input$generation_help,showModal(modalDialog(title='Generate one FMEA',
    p('Use the existing shared-key GitHub workflow in single mode. This dashboard does not make model calls or retry paid requests.'),
    a('Open Generate FMEA workflow',href='https://github.com/robertwarnold/sigmaairlinesproject/actions/workflows/generate-fmea.yml',target='_blank',rel='noopener noreferrer'),
    p('Select the correct skill branch, confirm one system and run, then explicitly authorize execution in GitHub. Synchronize receipts and explicitly import private V4 artifacts afterward.'),easyClose=TRUE)))
}
