scope_value <- function(x) if(is.null(x) || !length(x) || identical(x,'All')) NULL else x
historical_rounds <- c('v2.0'='1','v3.0'='2')
scope_dates <- function(dates) if(length(dates)==2 && !anyNA(dates) &&
  !identical(as.character(dates),c('2020-01-01',as.character(Sys.Date())))) dates

workspace_filters <- function(input) list(run=input$g_run,system=input$g_system,model=input$g_model,
  skill=input$g_skill,round=input$g_round,judge=input$g_judge,dates=scope_dates(input$g_dates),
  subsystem=input$g_subsystem,review=input$g_review)

select_historical_scope <- function(archive,system=NULL,skill=NULL,round=NULL) {
  if(is.null(archive) || !identical(archive$schema,'historical-comparison-1')) return(NULL)
  metrics <- if(is.null(system)) archive$metrics else archive$metrics_by_system[[system]]
  if(!is.null(skill)) metrics <- metrics[names(metrics)==skill]
  if(!is.null(round)) metrics <- metrics[which(historical_rounds[names(metrics)]==round)]
  list(source_sha256=archive$source_sha256,metrics=metrics)
}

scope_text <- function(system,round,skill,judge,dates,other,mapping) {
  active <- Filter(Negate(is.null),c(list(system,round,skill,judge,dates),other))
  system_label <- if(is.null(system)) 'All systems' else if(is.null(mapping$systems[[system]])) paste('System',system) else mapping$systems[[system]]
  paste(c(if(length(active)) 'Filtered selection' else 'All available records',system_label,
    if(is.null(round)) 'All rounds' else paste('Round',round),
    if(is.null(skill)) 'All generator versions' else skill,
    if(!is.null(judge)) paste('Judge',judge),
    if(!is.null(dates)) paste(format(dates),collapse=' to '),
    if(length(Filter(Negate(is.null),other))) 'Additional filters active'),collapse=' | ')
}
