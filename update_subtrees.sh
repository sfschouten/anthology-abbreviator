#!/usr/bin/env bash

# add dataset repos as remotes
git remote add -f acl_anthology_repo https://github.com/acl-org/acl-anthology.git

# pull the latest version of the repos
git subtree pull --prefix acl-anthology/ acl_anthology_repo master --squash

