experiment_identity <- function(record,workflow=list(),mapping=list()) {
  scalar <- function(x) if(length(x)==1L && !is.na(x) && nzchar(as.character(x))) as.character(x) else NULL
  first <- function(...) {
    values <- Filter(Negate(is.null),lapply(list(...),scalar))
    if(length(values)) values[[1]]
  }
  original <- first(record$original_filename,record$run_id)
  id <- first(record$generation_id,record$run_id)
  override <- mapping$aliases[[if(is.null(id)) '' else id]]
  parsed <- list()
  candidates <- unique(c(original,record$run_id,record$batch,sub('^.*:','',record$run_id)))
  for(candidate in candidates[!is.na(candidates)]) {
    for(rule in mapping$patterns) {
      match <- regmatches(basename(candidate),regexec(rule$pattern,basename(candidate),perl=TRUE,ignore.case=TRUE))[[1]]
      if(length(match)==length(rule$fields)+1L) {
        for(index in seq_along(rule$fields)) {
          field <- rule$fields[[index]]
          parsed[[field]] <- c(parsed[[field]],match[[index+1L]])
        }
      }
    }
  }
  system_values <- unique(toupper(sub('^system_','',c(record$manifest_system,record$system,workflow$system,parsed$system),ignore.case=TRUE)))
  round_values <- unique(suppressWarnings(as.integer(c(record$manifest_round,record$experiment_round,workflow$experiment_round,parsed$round))))
  run_values <- unique(suppressWarnings(as.integer(c(record$manifest_replicate,record$replicate,workflow$replicate,parsed$replicate))))
  system_values <- system_values[!is.na(system_values) & nzchar(system_values)]
  round_values <- round_values[!is.na(round_values) & round_values>0L]
  run_values <- run_values[!is.na(run_values) & run_values>0L]
  conflicts <- names(Filter(function(x) length(x)>1L,list(system=system_values,round=round_values,replicate=run_values)))
  system <- first(override$system,system_values[1])
  round <- first(override$round,round_values[1])
  replicate <- first(override$replicate,run_values[1])
  system_name <- if(!is.null(system)) first(mapping$systems[[system]],paste('System',system))
  label <- paste(if(is.null(system_name)) 'System unknown' else system_name,
    if(is.null(round)) 'Round unverified' else paste('Round',round),sep=' \u00b7 ')
  if(!is.null(replicate)) label <- paste(label,sprintf('Run %02d',as.integer(replicate)),sep=' \u00b7 ')
  list(label=label,id=id,system=system,system_name=system_name,round=round,replicate=replicate,conflicts=conflicts,
    generator_skill=first(record$skill_version),generator_model=first(record$generator_model),
    judge_version=first(record$judge_skill_version),branch=first(record$branch,workflow$branch),
    commit=first(record$git_commit,workflow$git_commit),workflow_run=first(record$parent_workflow_run_id,workflow$workflow_run_id),
    original_filename=scalar(record$original_filename),timestamp=scalar(record$generation_timestamp))
}

experiment_labels <- function(rows,mapping) vapply(seq_len(nrow(rows)),function(i)
  experiment_identity(as.list(rows[i,,drop=FALSE]),mapping=mapping)$label,character(1))

generation_duration_label <- function(seconds) {
  if(length(seconds)!=1L || is.na(seconds) || !is.finite(seconds) || seconds<0) return('Unavailable')
  if(seconds<60) return(sprintf('%.1f s',seconds))
  seconds <- round(seconds)
  minutes <- seconds %/% 60
  if(minutes<60) return(sprintf('%d min %02d s',minutes,seconds%%60))
  sprintf('%d h %02d min',minutes%/%60,minutes%%60)
}

with_manifest_identity <- function(record, manifest) {
  if(!nrow(manifest) || is.null(record$run_id)) return(record)
  i <- match(record$run_id,manifest$run_id)
  if(is.na(i)) return(record)
  record$manifest_system <- manifest$system[i]
  record$manifest_round <- if('experiment_round' %in% names(manifest)) manifest$experiment_round[i] else NULL
  record$manifest_replicate <- if('replicate' %in% names(manifest)) manifest$replicate[i] else NULL
  record
}
