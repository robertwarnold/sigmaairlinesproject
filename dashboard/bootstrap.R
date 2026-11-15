# Project-local dependencies keep the dashboard runnable without global R changes.
dashboard_dir <- if (file.exists('dashboard/plots.R')) 'dashboard' else '.'
project_root <- normalizePath(file.path(dashboard_dir, '..'), mustWork = TRUE)
local_library <- file.path(project_root, '.venv', 'r-library')
if (dir.exists(local_library)) .libPaths(c(local_library, .libPaths()))
