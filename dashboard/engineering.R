# Optional trusted local workstation. Never loaded into the public aggregate dataset.
engineering_allowed <- function(enabled,request) {
  identical(enabled,'1') && !is.null(request) &&
    !is.null(request$REMOTE_ADDR) && request$REMOTE_ADDR %in% c('127.0.0.1','::1','::ffff:127.0.0.1') &&
    !is.null(request$HTTP_HOST) && grepl('^(localhost|127\\.0\\.0\\.1|\\[::1\\])(:[0-9]+)?$',request$HTTP_HOST) &&
    (is.null(request$HTTP_ORIGIN) || grepl('^https?://(localhost|127\\.0\\.0\\.1|\\[::1\\])(:[0-9]+)?$',request$HTTP_ORIGIN)) &&
    is.null(request$HTTP_X_FORWARDED_FOR) && is.null(request$HTTP_FORWARDED)
}
engineering_ui <- function() shiny::uiOutput('engineering_body')
engineering_rpn_chart <- function(bins) {
  maximum <- max(1,bins$count)
  marks <- vapply(seq_len(nrow(bins)),function(i) {
    height <- 190*bins$count[i]/maximum
    mark('rect',paste0('x="',25+(i-1)*34,'" y="',225-height,'" width="28" height="',height,'" fill="',chart_tokens$accent,'"'),
      paste('RPN',bins$lower[i],'to',bins$upper[i],':',bins$count[i],'rows'))
  },character(1))
  svg_chart(c(marks,'<text x="25" y="258">1</text><text x="195" y="258">500</text><text x="365" y="258" text-anchor="end">1000</text><text x="25" y="280">RPN / 100-point bins; hover for row counts</text>'),
    'Current RPN distribution; row counts in 100-point bins, not probability or risk acceptance.',290)
}
engineering_notice <- function() chart_empty('Private FMEA workspace is disabled',
  'Use the local engineering launcher and explicitly import a generated V4 response. Reference worksheets are never imported.')
engineering_table <- function(rows,fields) {
  if(!nrow(rows)) return(chart_empty('No matching FMEA records','Adjust the run, review, severity or text filters.'))
  header <- htmltools::tags$thead(htmltools::tags$tr(lapply(fields,function(f) htmltools::tags$th(gsub('_',' ',f)))))
  body <- htmltools::tags$tbody(lapply(seq_len(nrow(rows)),function(i) {
    cells <- lapply(fields,function(f) htmltools::tags$td(if(is.na(rows[[f]][i])) 'Unknown' else as.character(rows[[f]][i])))
    htmltools::tags$tr(tabindex=0,class='engineering-row',`data-engineering-record`=rows$record_id[i],cells)
  }))
  htmltools::div(class='engineering-table-wrap',htmltools::tags$table(class='engineering-table',header,body))
}
engineering_server <- function(input,output,session) {
  allowed <- reactive(engineering_allowed(Sys.getenv('SIGMA_ENGINEERING_PRIVATE'),session$request))
  database <- Sys.getenv('SIGMA_ENGINEERING_DATABASE',file.path(project_root,'results','engineering','workspace.sqlite'))
  folder <- file.path(project_root,'results','engineering','ui',session$token)
  command <- function(action,args=character()) {
    req(allowed()); dir.create(folder,recursive=TRUE,showWarnings=FALSE)
    python <- Sys.getenv('SIGMA_PYTHON',file.path(project_root,'.venv','gemini','Scripts','python.exe'))
    if(!file.exists(python)) python <- Sys.which('python')
    previous <- getwd(); setwd(project_root); on.exit(setwd(previous),add=TRUE)
    log <- file.path(folder,'operation.log')
    status <- suppressWarnings(system2(python,c('-m','analysis.engineering','--database',shQuote(database),action,args),stdout=log,stderr=log))
    if(status!=0) stop('Operation rejected. Refresh stale records; verify required review fields, ratings and source hashes. Details are in the private workstation operation.log.')
  }
  tick <- reactiveVal(0)
  observeEvent(input$eng_refresh,{tick(tick()+1)})
  state <- reactivePoll(30000,session,checkFunc=function() {
    if(!allowed()) return('disabled')
    paste(tick(),if(file.exists(database)) file.info(database)$mtime else 'missing')
  },valueFunc=function() {
    if(!allowed() || !file.exists(database)) return(list(rows=data.frame(),records=list(),summary=NULL,comparisons=data.frame(),risk=NULL))
    path <- file.path(folder,'workspace.json'); command('snapshot',c('--output',shQuote(path)))
    jsonlite::fromJSON(path,simplifyDataFrame=TRUE)
  })
  all_rows <- reactive(as_table(state()$rows))
  output$engineering_body <- renderUI({
    if(!allowed()) return(engineering_notice())
    tagList(p(class='private-notice','Private workstation / generated drafts and human review. These records never enter public dashboard JSON.'),
      textOutput('eng_origin'),uiOutput('eng_summary'),
      div(class='engineering-controls',textInput('eng_search','Search records'),selectInput('eng_run','Run',choices='All'),
        selectInput('eng_review_filter','Review status',choices=c('All','NEEDS_REVIEW','APPROVED','REJECTED')),
        selectInput('eng_sort','Sort',choices=c('severity','RPN','component','failure_mode','review_status'))),
      tags$details(tags$summary('Advanced filters'),div(class='engineering-controls',
        selectInput('eng_system','System',choices='All'),selectInput('eng_subsystem','Subsystem',choices='All'),
        selectInput('eng_severity','Severity',choices=c('All',1:10)),selectInput('eng_occurrence','Occurrence',choices=c('All',1:10)),
        checkboxInput('eng_descending','Descending',TRUE))),
      div(class='engineering-exports',actionButton('eng_clear','Clear filters'),actionButton('eng_refresh','Refresh private data')),
      tags$details(tags$summary('Visible columns'),checkboxGroupInput('eng_columns','Columns',choices=c('system','subsystem','component','function','failure_mode','cause','local_effect','system_effect','severity','occurrence','detection','RPN','evidence_status','review_status','recommended_action'),
        selected=c('component','failure_mode','severity','occurrence','detection','RPN','evidence_status','review_status'),inline=TRUE)),
      uiOutput('eng_table'),numericInput('eng_page','Page',1,min=1,width='6rem'),
      div(class='engineering-exports',downloadButton('eng_csv','Export filtered CSV'),downloadButton('eng_json','Export filtered JSON')),
      selectInput('eng_record','Inspect a record',choices=character()),
      tabsetPanel(id='eng_detail',tabPanel('Assessment & evidence',uiOutput('eng_evidence')),
        tabPanel('Engineering review',uiOutput('eng_review_form'),actionButton('eng_save','Save review event'),textOutput('eng_save_status')),
        tabPanel('Change history',uiOutput('eng_history'))))
  })
  output$eng_origin <- renderText({
    if(!allowed()) return('')
    r <- as_table(state()$comparisons)
    if(nrow(r) && any(grepl('synthetic|demo',r$data_origin,ignore.case=TRUE))) 'SYNTHETIC TEST DATA / NOT RESEARCH FINDINGS' else 'Imported V4 generated outputs; engineer approval is distinct from independent judge evaluation.'
  })
  output$eng_summary <- renderUI({
    req(allowed()); s <- state()$summary
    if(is.null(s)) return(chart_empty('No imported engineering records','Import a hash-bound generated V4 response with the private CLI, then refresh.'))
    div(class='kpi-row',div(class='kpi',strong(s$generated_rows),span('Imported failure-mode rows')),
      div(class='kpi',strong(s$unique_rows_within_runs),span('Unique within runs')),
      div(class='kpi',strong(s$high_severity_rows),span('High severity / S >= 9')),
      div(class='kpi',strong(s$needs_review),span('Needs engineering review')),
      tags$details(class='metric-definitions',tags$summary('Validation and evidence definitions'),
        p(paste('Original structural pass:',fmt(s$original_structural_pass_percentage,'%'),'/ cited evidence:',fmt(s$cited_evidence_percentage,'%'))),p(s$basis)))
  })
  observeEvent(list(all_rows(),input$eng_sort),{
    req(input$eng_sort); r <- all_rows(); if(!nrow(r)) return()
    preserve <- function(id,choices) {v <- isolate(input[[id]]); if(is.null(v)||!v %in% choices) choices[1] else v}
    for(pair in list(c('eng_run','run_id'),c('eng_system','system'),c('eng_subsystem','subsystem'))) {
      choices <- c('All',sort(unique(r[[pair[2]]]))); updateSelectInput(session,pair[1],choices=choices,selected=preserve(pair[1],choices))
    }
    choices <- setNames(r$record_id,paste(r$row_id,r$component,r$failure_mode,sep=' / '))
    selected <- isolate(input$eng_record); if(is.null(selected)||!selected %in% r$record_id) selected <- r$record_id[1]
    updateSelectInput(session,'eng_record',choices=choices,selected=selected)
  })
  observeEvent(input$eng_clear,{
    updateTextInput(session,'eng_search',value=''); for(id in c('eng_run','eng_system','eng_subsystem','eng_severity','eng_occurrence','eng_review_filter')) updateSelectInput(session,id,selected='All')
    updateNumericInput(session,'eng_page',value=1)
  })
  filtered <- reactive({
    r <- all_rows(); if(!nrow(r)) return(r)
    keep <- rep(TRUE,nrow(r))
    for(pair in list(c('eng_run','run_id'),c('eng_system','system'),c('eng_subsystem','subsystem'),c('eng_severity','severity'),c('eng_occurrence','occurrence'),c('eng_review_filter','review_status'))) {
      v <- input[[pair[1]]]; if(!is.null(v)&&v!='All') keep <- keep & !is.na(r[[pair[2]]]) & as.character(r[[pair[2]]])==v
    }
    if(!is.null(input$eng_search)&&nzchar(input$eng_search)) keep <- keep & apply(r,1,function(x) any(grepl(input$eng_search,x,fixed=TRUE),na.rm=TRUE))
    r <- r[which(keep),,drop=FALSE]; key <- input$eng_sort
    if(!is.null(key)&&key %in% names(r)) r <- r[order(r[[key]],decreasing=isTRUE(input$eng_descending),na.last=TRUE),,drop=FALSE]
    r
  })
  output$eng_table <- renderUI({
    req(allowed()); r <- filtered(); fields <- intersect(input$eng_columns,names(r))
    if(!length(fields)) return(p('Select at least one column.'))
    page <- input$eng_page; if(is.null(page)||!is.finite(page)) page <- 1
    page <- max(1,min(ceiling(nrow(r)/10),floor(page))); start <- (page-1)*10
    tagList(engineering_table(utils::head(r[seq_len(nrow(r))>start,,drop=FALSE],10),fields),p(class='chart-note',paste(nrow(r),'matching rows. Click a row to inspect its original assessment and review history.')))
  })
  observeEvent(input$eng_pick,{updateSelectInput(session,'eng_record',selected=input$eng_pick)})
  # Reading one record without dataframe simplification avoids lossy scalar/list coercion.
  record_index <- reactive({
    if(!allowed()||!file.exists(file.path(folder,'workspace.json'))) return(list())
    state(); records <- jsonlite::fromJSON(file.path(folder,'workspace.json'),simplifyVector=FALSE)$records
    setNames(records,vapply(records,function(r) r$record_id,character(1)))
  })
  record <- reactive({if(is.null(input$eng_record)) NULL else record_index()[[input$eng_record]]})
  output$eng_evidence <- renderUI({
    req(allowed()); r <- record(); if(is.null(r)) return(p('Select an imported record.'))
    text <- function(x) if(is.null(x)||!length(x)) 'Not provided' else paste(unlist(x),collapse=', ')
    assessment <- function(title,row,score) tags$section(class='engineering-assessment',h3(title),
      tags$dl(lapply(c('component','function','failure_mode','cause','local_effect','system_effect','recommended_action'),function(k)
        tagList(tags$dt(gsub('_',' ',k)),tags$dd(text(row[[k]]))))),
      p(paste('Severity',text(row$severity),'/ Occurrence',text(row$occurrence),'/ Detection',text(row$detection),'/ RPN',text(score))))
    tagList(div(class='chart-grid-layout',assessment('Original AI draft',r$original,r$original_validation$computed_rpn),
      assessment('Current assessment / reviewed values',r$current,r$validation$computed_rpn)),
      div(class='engineering-facts',h3('Evidence and traceability'),
        p(paste('Input package SHA:',r$metadata$dataset_id,'/ unit:',r$original$unit_id)),
        strong('Input-package fact'),tags$blockquote(text(r$unit$evidence)),
        strong('AI-provided citation / unverified until engineering review'),p(text(r$current$evidence)),
        strong('AI assumptions'),p(text(r$current$assumptions)),
        p(paste('Human review:',r$review_status,'/ basis:',text(r$review_basis))),
        p(paste('Structure:',r$validation$structural_status,'/ provisional S/O/D scale 1-10; high severity is independent of RPN')),
        tags$ul(lapply(c(unlist(r$validation$errors),unlist(r$validation$review_flags)),tags$li))),
      tags$details(tags$summary('Full provenance, relationships and immutable source JSON'),
        tags$pre(jsonlite::toJSON(list(original=r$original,current=r$current,unit=r$unit,metadata=r$metadata),pretty=TRUE,auto_unbox=TRUE,null='null'))),
      p(class='chart-note','Human-approved inference is distinct from source verification. No calibrated probability or residual-risk claim is implied. Reference FMEAs are never opened.'))
  })
  output$eng_review_form <- renderUI({
    req(allowed()); r <- record(); if(is.null(r)) return(NULL)
    tagList(p(paste('Revision',r$revision,'/',r$review_status)),textInput('eng_reviewer','Engineer / reviewer name'),textAreaInput('eng_note','Review note / rationale'),
      selectInput('eng_decision','Decision',choices=c('Needs review / reopen'='NEEDS_REVIEW','Approve'='APPROVED','Reject'='REJECTED')),
      selectInput('eng_basis','Engineering basis',choices=c('Select a basis'='', 'Human-verified source citation'='source_verified','Human-approved inference'='approved_inference')),
      checkboxInput('eng_confirm','I reviewed the causal chain, assumptions, ratings and recommended action',FALSE),
      checkboxInput('eng_edit','Apply corrections below (original AI values remain unchanged)',FALSE),
      div(class='assumption-grid',lapply(c('severity','occurrence','detection'),function(k) textInput(paste0('eng_edit_',k),paste(k,'(1-10; blank = missing)'),value=if(is.null(r$current[[k]])) '' else r$current[[k]]))),
      lapply(c('cause','local_effect','system_effect','recommended_action','evidence','assumptions'),function(k) textAreaInput(paste0('eng_edit_',k),gsub('_',' ',k),value=r$current[[k]])),
      div(class='engineering-controls',selectInput('eng_action_status','Action status',choices=c('Not recorded'='', 'Open'='OPEN','In progress'='IN_PROGRESS','Complete'='COMPLETE'),selected=if(is.null(r$current$action_status)) '' else r$current$action_status),
        textInput('eng_action_due','Action due date (YYYY-MM-DD)',value=if(is.null(r$current$action_due_date)) '' else r$current$action_due_date),
        textInput('eng_action_owner','Action owner',value=if(is.null(r$current$action_owner)) '' else r$current$action_owner)),
      p(class='chart-note','Approval requires valid structure and explicit engineering confirmation. Reopen an approved/rejected record before further decisions.'))
  })
  output$eng_history <- renderUI({req(allowed()); r <- record(); if(is.null(r)) return(NULL); tags$pre(jsonlite::toJSON(r$history,pretty=TRUE,auto_unbox=TRUE,null='null'))})
  save_status <- reactiveVal('')
  output$eng_save_status <- renderText(save_status())
  observeEvent(input$eng_save,{
    req(allowed()); r <- record(); req(r)
    tryCatch({
      corrections <- list()
      if(isTRUE(input$eng_edit)) {
        for(k in c('severity','occurrence','detection')) {
          v <- trimws(input[[paste0('eng_edit_',k)]]); if(nzchar(v)&&!grepl('^([1-9]|10)$',v)) stop('Ratings must be whole numbers 1-10 or blank; no default ratings are substituted.')
          corrections[k] <- list(if(nzchar(v)) as.integer(v) else NULL)
        }
        for(k in c('cause','local_effect','system_effect','recommended_action','evidence','assumptions')) corrections[[k]] <- input[[paste0('eng_edit_',k)]]
        corrections$action_status <- input$eng_action_status; corrections$action_due_date <- input$eng_action_due; corrections$action_owner <- input$eng_action_owner
      }
      request <- list(record_id=r$record_id,expected_revision=r$revision,state=input$eng_decision,reviewer=input$eng_reviewer,note=input$eng_note,
                      corrections=if(length(corrections)) corrections else NULL,basis=input$eng_basis,engineering_confirmed=isTRUE(input$eng_confirm))
      path <- file.path(folder,'review-request.json'); jsonlite::write_json(request,path,auto_unbox=TRUE,null='null',digits=NA)
      command('review',c('--request',shQuote(path))); tick(tick()+1); save_status('Review event saved. Original assessment preserved.')
    },error=function(e) save_status(conditionMessage(e)))
  })
  for(kind in c('csv','json')) local({
    format <- kind
    output[[paste0('eng_',format)]] <- downloadHandler(filename=function() paste0('private-reviewed-fmea.',format),content=function(file) {
      req(allowed()); ids <- as.list(filtered()$record_id); selection <- tempfile(tmpdir=folder,fileext='.json'); stage <- tempfile(tmpdir=folder,fileext=paste0('.',format))
      jsonlite::write_json(ids,selection,auto_unbox=TRUE); command('export',c('--format',format,'--selection',shQuote(selection),'--output',shQuote(stage)))
      file.copy(stage,file,overwrite=TRUE)
    })
  })
  output$engineering_risk <- renderUI({
    if(!allowed()) return(engineering_notice())
    d <- state(); if(is.null(d$risk)) return(chart_empty('No private risk data','Import generated V4 records before analyzing row-level risk.'))
    risk <- d$risk$current; matrix <- as_table(risk$matrix); body <- character()
    for(s in 1:10) for(o in 1:10) {
      value <- if(nrow(matrix)) matrix$count[matrix$severity==s & matrix$occurrence==o] else numeric()
      n <- if(length(value)) value[1] else 0
      body <- c(body,paste0('<rect x="',25+(o-1)*34,'" y="',15+(10-s)*22,'" width="30" height="18" fill="',if(n) chart_tokens$accent else chart_tokens$raised,'" data-engineering-cell="',s,',',o,'" tabindex="0" role="button" aria-label="Severity ',s,', occurrence ',o,': ',n,' rows"><title>S ',s,' / O ',o,' / ',n,' rows</title></rect>'))
      if(n) body <- c(body,paste0('<text x="',40+(o-1)*34,'" y="',28+(10-s)*22,'" text-anchor="middle" style="fill:#0B1016">',n,'</text>'))
    }
    body <- c(body,'<text x="25" y="258">Occurrence 1 to 10 (left to right)</text><text x="25" y="280">Severity 10 to 1 (top to bottom)</text>')
    h <- as_table(risk$rpn_bins); sub <- as_table(risk$subsystems); cats <- as_table(risk$categories)
    tagList(p(class='private-notice','Private current reviewed assessments / row counts, not physical failure frequency or formal risk acceptance.'),
      div(class='chart-grid-layout',chart_panel('Severity versus occurrence',svg_chart(body,'Distribution of row ratings on the existing 1-10 scale. Select a cell to inspect matching records.',290)),
        chart_panel('RPN distribution',tagList(engineering_rpn_chart(h),chart_details(h,'RPN bin counts')))),
      p(paste(risk$missing_rpn_rows,'rows have no valid RPN. High severity requires attention even with low RPN.')),
      tags$details(tags$summary('Subsystems, failure categories and action tracking'),
        chart_panel('Subsystem row counts',bar_rows(sub$name,sub$count,max(1,sub$count))),
        chart_panel('Pareto: generated row categories (not failure frequency)',bar_rows(cats$name,cats$count,max(1,cats$count))),
        if(nrow(as_table(risk$actions))) chart_details(as_table(risk$actions),'Recorded actions') else p('No action-status records. Recommended actions do not establish completion.'),
        p('Original versus reviewed ratings are available per record. No residual risk or mitigation effectiveness is inferred.')),
      uiOutput('eng_comparisons'))
  })
  observeEvent(input$eng_risk_cell,{
    pieces <- strsplit(input$eng_risk_cell,',',fixed=TRUE)[[1]]; req(length(pieces)==2,all(pieces %in% as.character(1:10)))
    for(id in c('eng_run','eng_system','eng_subsystem','eng_review_filter')) updateSelectInput(session,id,selected='All')
    updateTextInput(session,'eng_search',value=''); updateSelectInput(session,'eng_severity',selected=pieces[1]); updateSelectInput(session,'eng_occurrence',selected=pieces[2])
    updateTabsetPanel(session,'view',selected='Experiment explorer'); updateTabsetPanel(session,'explorer_mode',selected='workspace')
  })
  output$eng_comparisons <- renderUI({
    req(allowed()); r <- as_table(state()$comparisons); if(!nrow(r)) return(NULL)
    # Separate condition groups, never pool incompatible input datasets or scoring scales.
    tags$details(tags$summary('Comparable engineering runs / metadata'),lapply(split(r,r$comparison_key),function(group) {
      cols <- intersect(c('run_id','dataset_version','generator_model','skill_version','scoring_policy','generated_rows','duplicate_percentage','approved_rows','reviewed_rows','generation_seconds','estimated_cost'),names(group))
      chart_details(group[,cols,drop=FALSE],paste('Compatible group',substr(group$comparison_key[1],1,12)))
    }),p('V4.1 and V4.2 are dashboard revisions, not new FMEA skill treatments. Reference recall, precision and unsupported-assertion rates remain unavailable without independent evaluations.'))
  })
}
