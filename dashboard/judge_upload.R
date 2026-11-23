# Judge artifacts stay on a trusted workstation. The public mode has no upload action.
judge_upload_server <- function(input,output,session,refresh) {
  allowed <- function() engineering_allowed(Sys.getenv('SIGMA_ENGINEERING_PRIVATE'),session$request)
  folder <- file.path(project_root,'results','research','uploads',session$token)
  database <- file.path(project_root,'results','research','registry.sqlite')
  staged <- reactiveVal(NULL)
  output$judge_import_action <- renderUI({
    if(allowed()) tagList(actionButton('github_sync_open','Sync GitHub'),
      actionButton('judge_import_open','Import Judge Results'))
  })

  run_import <- function(action,args) {
    req(allowed())
    python <- Sys.getenv('SIGMA_PYTHON',file.path(project_root,'.venv','gemini','Scripts','python.exe'))
    if(!file.exists(python)) python <- Sys.which('python')
    if(!nzchar(python)) stop('Configure the workstation Python interpreter.')
    previous <- getwd()
    setwd(project_root)
    on.exit(setwd(previous),add=TRUE)
    log <- tempfile(tmpdir=folder,fileext='.log')
    result <- tempfile(tmpdir=folder,fileext='.json')
    status <- suppressWarnings(system2(python,c('-m','analysis.research','--database',shQuote(database),
      action,args),stdout=result,stderr=log))
    if(status!=0) {
      details <- tail(readLines(log,warn=FALSE),1)
      message <- if(length(details)) substr(details,1,300) else 'Check the private operation log.'
      stop(message,call.=FALSE)
    }
    jsonlite::fromJSON(result)
  }

  observeEvent(input$github_sync_open,{
    req(allowed())
    dir.create(folder,recursive=TRUE,showWarnings=FALSE)
    tryCatch({
      branches <- run_import('sync','--list-branches')$branch
      branches <- branches[grepl('^[A-Za-z0-9][A-Za-z0-9._/-]*$',branches)]
      showModal(modalDialog(title='Sync GitHub',
        selectizeInput('github_branches','Branches',choices=branches,multiple=TRUE),
        p('Select branches to synchronize generation workflow metadata and available execution receipts.'),
        textOutput('github_sync_status'),
        footer=tagList(modalButton('Close'),actionButton('github_sync_confirm','Synchronize',class='btn-primary'))))
    },error=function(e) showNotification(conditionMessage(e),type='error'))
  })
  sync_status <- reactiveVal('')
  output$github_sync_status <- renderText(sync_status())
  observeEvent(input$github_sync_confirm,{
    req(allowed(),input$github_branches)
    branches <- input$github_branches
    req(all(grepl('^[A-Za-z0-9][A-Za-z0-9._/-]*$',branches)))
    tryCatch({
      result <- run_import('sync',c('--no-render',as.vector(rbind('--branch',branches))))
      sync_status(paste('Status',result$status,'· Last successful refresh',
        if(is.null(result$last_successful_sync)) 'pending' else result$last_successful_sync,
        '· Import issues',NROW(result$problems)))
      refresh()
    },error=function(e) sync_status(conditionMessage(e)))
  })

  observeEvent(input$judge_import_open,{
    req(allowed())
    staged(NULL)
    status_text('')
    showModal(modalDialog(title='Import Judge Results',
      fileInput('judge_primary','Judge results',accept=c('.json','.csv','.xlsx','.zip')),
      fileInput('judge_items','Item results for paired CSV',accept='.csv'),
      p('Use identifier-only judge exports. ZIP uploads accept judge.json, judge.xlsx, or runs.csv and items.csv at the archive root.'),
      textOutput('judge_preview_status'),tableOutput('judge_preview_table'),
      footer=tagList(modalButton('Close'),actionButton('judge_preview','Preview'),uiOutput('judge_confirm_action',inline=TRUE))))
  })

  observeEvent(list(input$judge_primary,input$judge_items),staged(NULL),ignoreInit=TRUE)
  status_text <- reactiveVal('')
  output$judge_preview_status <- renderText(status_text())
  output$judge_preview_table <- renderTable({
    req(staged())
    staged()$preview$records
  })
  output$judge_confirm_action <- renderUI({
    if(!is.null(staged())) actionButton('judge_confirm','Confirm import',class='btn-primary')
  })

  observeEvent(input$judge_preview,{
    req(allowed(),input$judge_primary)
    staged(NULL)
    status_text('')
    tryCatch({
      dir.create(folder,recursive=TRUE,showWarnings=FALSE)
      stage_file <- function(file,extensions) {
        suffix <- tolower(tools::file_ext(file$name))
        if(!suffix %in% extensions || file$size > 20000000) stop('Choose a supported file up to 20 MB.')
        destination <- tempfile(tmpdir=folder,fileext=paste0('.',suffix))
        if(!file.copy(file$datapath,destination)) stop('Could not stage the uploaded file.')
        shQuote(destination)
      }
      args <- c('--file',stage_file(input$judge_primary,c('json','csv','xlsx','zip')))
      if(!is.null(input$judge_items)) args <- c(args,'--items',stage_file(input$judge_items,'csv'))
      preview <- run_import('preview-judge',args)
      staged(list(args=args,preview=preview))
      status_text('Review the matched generation and evaluation IDs before confirming.')
    },error=function(e) status_text(conditionMessage(e)))
  })

  observeEvent(input$judge_confirm,{
    req(allowed(),staged())
    tryCatch({
      entry <- staged()
      run_import('accept-judge',c('--no-render',entry$args,'--confirm-sha256',entry$preview$confirmation_sha256))
      staged(NULL)
      removeModal()
      refresh()
      showNotification('Judge results imported.',type='message')
    },error=function(e) status_text(conditionMessage(e)))
  })
  session$onSessionEnded(function() {
    if(dir.exists(folder)) unlink(folder,recursive=TRUE)
  })
}
