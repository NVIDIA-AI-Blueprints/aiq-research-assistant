<!--
SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

### DELETE PRIOR TO GOING LIVE
---

### Overview

The .github folder houses:
- Issue templates
- PR template
- GitHub Actions
- Codeowners

#### Issue Templates
These are the templates a user sees if they click `New Issue`. This repo has provided two template styles:
1. `.md` templates
   - These are the simpler templates, use these as a _starting point_ for lightweight repos
1. `.yml` templates
   - These are more complex `form` templates, they are clearer in what we expect from the user and are preferred when possible as we can enforce required fields

Regardless of the issue template selected, some customization for each library is expected:
- Default assignees
- Default labels
- Do the prompts make sense for your repo?

> **Warning**
> 
> Be sure to delete whichever templates you are not using


#### PR Template
This is the default template that users see when they go to open a new PR in the repo. Customize as needed to fit the repo. Currently, there are no form-style PR templates, only plain markdown templates.

#### GitHub Actions
GitHub Actions are automations that are triggered on specific events. Some commonly used actions:
- Run CI
- Auto-add issues to projects
- Auto-label external contributor issues/PRs

#### Codeowners
This file defines individuals or teams that are responsible for code in a repository, you'll need to set up your teams first in the org, then add them to the codeowners. We're provided a template CODEOWNERS file here.
