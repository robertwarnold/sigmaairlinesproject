library(gert)
library(credentials)

# Configure Git commit identity
gert::git_config_global_set("user.name", "Robert Arnold")
gert::git_config_global_set("user.email", "robertwarnold13@gmail.com")

credentials::set_github_pat()
# prompts a popup asking you to enter your GitHub Personal Access Token

gert::git_pull()                          # pull the most recent changes from GitHub
gert::git_add(dir(all.files = TRUE))      # stage every new or edited file
gert::git_commit_all("my first commit")   # save your record of the edits (a commit)
gert::git_push()                          # push your commit up to GitHub
