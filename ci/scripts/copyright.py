#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2019-2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import datetime
import io
import logging
import os
import re
import sys

# Now import gitutils. Ignore flake8 error here since there is no other way to
# set up imports
import gitutils  # noqa: E402

# pylint: disable=global-statement

logger = logging.getLogger(__name__)

FilesToCheck = [
    # Get all of these extensions and templates (*.in)
    re.compile(r"[.](cmake|cpp|cc|cu|cuh|h|hpp|md|rst|sh|pxd|py|pyx|yml|yaml)(\.in)?$"),
    # And files with a particular file/extension combo
    re.compile(r"CMakeLists[.]txt$"),
    re.compile(r"setup[.]cfg$"),
    re.compile(r"[.]flake8[.]cython$"),
    re.compile(r"meta[.]yaml$"),
    re.compile(r"[^ \/\n]*Dockerfile[^ \/\n]*")
]

# Nothing in a build folder or .cache
ExemptFiles: list[re.Pattern] = [
    re.compile(r"(_version|versioneer)\.py"),  # Skip versioning files
    re.compile(r"^[^ \/\n]*\.cache[^ \/\n]*\/.*$"),  # Ignore .cache folder
    re.compile(r"^[^ \/\n]*build[^ \/\n]*\/.*$"),  # Ignore any build*/ folder
    re.compile(r"^external\/.*$"),  # Ignore external
    re.compile(r"[^ \/\n]*docs/source/(_lib|_modules|_templates)/.*$"),
    re.compile(r"PULL_REQUEST_TEMPLATE.md"),  # Ignore the PR template,
    re.compile(r"[^ \/\n]*conda/environments/.*\.yaml$"),  # Ignore generated environment files
    re.compile(r"^LICENSE\.md$"),  # Ignore the license file itself,
]

# this will break starting at year 10000, which is probably OK :)
CheckSimple = re.compile(r"Copyright *(?:\(c\))? *(\d{4}),? *NVIDIA C(?:ORPORATION|orporation)")
CheckDouble = re.compile(r"Copyright *(?:\(c\))? *(\d{4})-(\d{4}),? *NVIDIA C(?:ORPORATION|orporation)")
CHECK_APACHE_LIC = 'Licensed under the Apache License, Version 2.0 (the "License");'


def is_file_empty(f):
    return os.stat(f).st_size == 0


def check_this_file(f):
    # This check covers things like symlinks which point to files that DNE
    if not (os.path.exists(f)):
        return False
    if is_file_empty(f):
        return False
    for exempt in ExemptFiles:
        if exempt.search(f):
            return False
    for checker in FilesToCheck:
        if checker.search(f):
            return True
    return False


def get_copyright_years(line):
    res = CheckSimple.search(line)
    if res:
        return (int(res.group(1)), int(res.group(1)))
    res = CheckDouble.search(line)
    if res:
        return (int(res.group(1)), int(res.group(2)))
    return (None, None)


def replace_current_year(line, start, end):
    # first turn a simple regex into double (if applicable). then update years
    res = CheckSimple.sub(r"Copyright (c) \1-\1, NVIDIA CORPORATION", line)

    # pylint: disable=consider-using-f-string
    res = CheckDouble.sub(r"Copyright (c) {:04d}-{:04d}, NVIDIA CORPORATION".format(start, end), res)
    return res


def insert_license(f, this_year, first_line):
    ext = os.path.splitext(f)[1].lstrip('.')

    if ext == "" and os.path.basename(f) == "Dockerfile":
        ext = "Dockerfile"

    try:
        license_text = EXT_LIC_MAPPING[ext].format(YEAR=this_year)
    except KeyError:
        return [
            f,
            0,
            f"Unsupported extension {ext} for automatic insertion, "
            "please manually insert an Apache v2.0 header or add the file to "
            "excempted from this check add it to the 'ExemptFiles' list in "
            "the 'ci/scripts/copyright.py' file (manual fix required)",
            None
        ]

    # If the file starts with a #! keep it as the first line
    if first_line.startswith("#!"):
        replace_line = first_line + license_text
    else:
        replace_line = f"{license_text}\n{first_line}"

    return [f, 1, "License inserted", replace_line]


def check_copyright(  # pylint: disable=too-many-positional-arguments
        f,
        update_current_year,
        verify_apache_v2=False,
        update_start_year=False,
        do_insert_license=False,
        git_add=False):
    """
    Checks for copyright headers and their years
    """
    errs = []
    this_year = datetime.datetime.now().year
    line_num = 0
    cr_found = False
    apache_lic_found = not verify_apache_v2
    year_matched = False
    with io.open(f, "r", encoding="utf-8") as file:
        lines = file.readlines()
    for line in lines:
        line_num += 1
        if not apache_lic_found:
            apache_lic_found = CHECK_APACHE_LIC in line

        start, end = get_copyright_years(line)
        if start is None:
            continue

        cr_found = True
        if update_start_year:
            try:
                git_start = gitutils.get_file_add_date(f).year
                if start > git_start:
                    e = [
                        f,
                        line_num,
                        "Current year not included in the "
                        "copyright header",
                        replace_current_year(line, git_start, this_year)
                    ]
                    errs.append(e)
                    continue

            except Exception as excp:
                e = [f, line_num, f"Error determining start year from git: {excp}", None]
                errs.append(e)
                continue

        if start > end:
            e = [f, line_num, "First year after second year in the copyright header (manual fix required)", None]
            errs.append(e)
        if this_year < start or this_year > end:
            e = [f, line_num, "Current year not included in the copyright header", None]
            if this_year < start:
                e[-1] = replace_current_year(line, this_year, end)
            if this_year > end:
                e[-1] = replace_current_year(line, start, this_year)
            errs.append(e)
        else:
            year_matched = True
    file.close()

    if not apache_lic_found:
        if do_insert_license and len(lines):
            e = insert_license(f, this_year, lines[0])
            cr_found = True
            year_matched = True
        else:
            e = [
                f,
                0,
                "Apache copyright header missing, if this file needs to be "
                "excempted from this check add it to the 'ExemptFiles' list in "
                "the 'ci/scripts/copyright.py' file.",
                True
            ]
        errs.append(e)

    # copyright header itself not found
    if not cr_found:
        e = [f, 0, "Copyright header missing or formatted incorrectly (manual fix required)", None]
        errs.append(e)

    # even if the year matches a copyright header, make the check pass
    if year_matched and apache_lic_found:
        errs = []

    if update_current_year or update_start_year or do_insert_license:
        errs_update = [x for x in errs if x[-1] is not None]
        if len(errs_update) > 0:
            logger.info("File: %s. Changing line(s) %s", f, ', '.join(str(x[1]) for x in errs if x[-1] is not None))
            for _, line_num, __, replacement in errs_update:
                lines[line_num - 1] = replacement
            with io.open(f, "w", encoding="utf-8") as out_file:
                for new_line in lines:
                    out_file.write(new_line)

            if git_add:
                gitutils.add_files(f)

        errs = [x for x in errs if x[-1] is None]

    return errs


def _main():
    """
    Checks for copyright headers in all the modified files. In case of local
    repo, this script will just look for uncommitted files and in case of CI
    it compares between branches "$PR_TARGET_BRANCH" and "current-pr-branch"
    """
    log_level = logging.getLevelName(os.environ.get("AIQ_LOG_LEVEL", "INFO"))
    logging.basicConfig(format="%(levelname)s:%(message)s", level=log_level)

    ret_val = 0
    global ExemptFiles

    argparser = argparse.ArgumentParser("Checks for a consistent copyright header in git's modified files")
    argparser.add_argument("--update-start-year",
                           dest="update_start_year",
                           action="store_true",
                           help="Forces the start year to be the one from 'git log'")
    argparser.add_argument("--update-current-year",
                           dest="update_current_year",
                           action="store_true",
                           help="Forces the current year to be this year")
    argparser.add_argument("--insert-license",
                           dest="insert_license",
                           action="store_true",
                           help="Inserts a license block if one is not found")
    argparser.add_argument("--git-add",
                           dest='git_add',
                           action='store_true',
                           help="Runs 'git add' on any files that are modified by this script")
    argparser.add_argument("--exempt-files-list",
                           nargs='*',
                           dest="exempt_files_list",
                           help="Exempts a list of files from the copyright check")
    argparser.add_argument("--verify-apache-v2",
                           dest="verify_apache_v2",
                           action="store_true",
                           help="Verifies that the file contains the Apache v2 license boilerplate text")
    args = argparser.parse_args()

    # if a list of files is passed, this will be used instead of git
    if args.exempt_files_list:
        logger.info("Adding %s to the exempt list", ', '.join(args.exempt_files_list))
        ExemptFiles.extend([re.compile(x) for x in args.exempt_files_list])

    files = gitutils.get_git_modified_files()
    if not files:
        logger.info("No files to check")
        sys.exit(ret_val)

    errors = []
    for f in files:
        if not check_this_file(f):
            continue
        try:
            errors.extend(
                check_copyright(f, args.update_current_year, args.verify_apache_v2, args.update_start_year,
                                args.insert_license, args.git_add))
        except Exception as e:  # pylint: disable=broad-except
            ret_val = 1
            logger.error("Error when checking file %s: %s", f, e)

    if len(errors) > 0:
        ret_val = 1
        print("Copyright check failed for the following files:")
        for e in errors:
            print("  %s:%d -- %s" % (e[0], e[1], e[2]))

    else:
        print("Copyright check passed")

    sys.exit(ret_val)


# Maps the file extension to the license header
# Key is the extension, value is a tuple of (header, footer)
# We use a tuple to allow for future use of footers
# Note: Python and Shell scripts use a program invocation line
# (e.g. #!/usr/bin/env python) which should not be replaced.
# The logic in 'insert_license_header' is aware of this.
EXT_LIC_MAPPING = {
    "c":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "cmake":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law of or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "cpp":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "cu":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "cuh":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "Dockerfile":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "h":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
a *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "hpp":
        """/*
 * SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,

 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
""",
    "in":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "md":
        """<!--
SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
""",
    "pxd":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law of or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "py":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "pyx":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "rst":
        """..
  SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
""",
    "sh":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
    "yaml":
        """#
# SPDX-FileCopyrightText: Copyright (c) {YEAR}, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""",
}

if __name__ == "__main__":
    _main()
