import json
import os
import re
import urllib.request

API_URL = "https://api.easi.utoronto.ca/ttb/getPageableCourses"

# 你要监控的课程
COURSE_CODE = "WGS397H1"
SESSION = "20269"       # Fall 2026
DIVISION = "ARTSC"      # UTSG Faculty of Arts & Science
SECTION_PREFIX = "LEC"

payload = {
    "courseCodeAndTitleProps": {
        "courseCode": COURSE_CODE,
        "courseTitle": "",
        "courseSectionCode": ""
    },
    "departmentProps": [],
    "campuses": [],
    "sessions": [SESSION],
    "requirementProps": [],
    "instructor": "",
    "courseLevels": [],
    "deliveryModes": [],
    "dayPreferences": [],
    "timePreferences": [],
    "divisions": [DIVISION],
    "creditWeights": [],
    "availableSpace": False,
    "waitListable": False,
    "page": 1,
    "pageSize": 20,
    "direction": "asc"
}

request = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Origin": "https://ttb.utoronto.ca",
        "Referer": "https://ttb.utoronto.ca/",
        "User-Agent": "uoft-seat-monitor/1.0"
    },
    method="POST"
)

with urllib.request.urlopen(request, timeout=30) as response:
    text = response.read().decode("utf-8", errors="replace")

start_marker = "<courses><courses>"
end_marker = "<cmCourseInfo>"

start = text.find(start_marker)
end = text.find(end_marker, start if start >= 0 else 0)

if start >= 0 and end > start:
    course_block = text[start:end]
else:
    course_block = text

if COURSE_CODE.lower() not in course_block.lower():
    raise RuntimeError(
        f"Could not find {COURSE_CODE} in the Timetable Builder response."
    )

section_pattern = re.compile(
    rf"{re.escape(SECTION_PREFIX)}\d{{4}}",
    re.IGNORECASE
)

sections = []
seen = set()

for match in section_pattern.finditer(course_block):
    name = match.group(0).upper()

    if name not in seen:
        seen.add(name)
        sections.append((name, match.start()))

if not sections:
    raise RuntimeError(
        f"No lecture sections found for {COURSE_CODE}."
    )


def value_after(tag, start_pos):
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"

    a = course_block.find(open_tag, start_pos)

    if a < 0:
        return None

    b = course_block.find(
        close_tag,
        a + len(open_tag)
    )

    if b < 0:
        return None

    return course_block[
        a + len(open_tag):b
    ].strip()


statuses = []
open_sections = []

for section, pos in sections:

    current_raw = value_after(
        "currentEnrolment",
        pos
    )

    maximum_raw = value_after(
        "maxEnrolment",
        pos
    )

    open_status = value_after(
        "openLimitInd",
        pos
    )

    if current_raw is None or maximum_raw is None:
        continue

    try:
        current = int(current_raw)
        maximum = int(maximum_raw)
    except ValueError:
        continue

    spots = max(maximum - current, 0)

    status = {
        "section": section,
        "current": current,
        "maximum": maximum,
        "spots": spots,
        "open_status": open_status or ""
    }

    statuses.append(status)

    if (
        spots > 0
        and (open_status or "").upper() != "C"
    ):
        open_sections.append(status)


if not statuses:
    raise RuntimeError(
        "Could not read enrolment numbers."
    )


print(f"Checking {COURSE_CODE}")

for s in statuses:
    print(
        f"{s['section']}: "
        f"{s['current']}/{s['maximum']} "
        f"({s['spots']} spots)"
    )


if open_sections:

    lines = [
        "🚨 WGS397H1F HAS AN OPEN SEAT!",
        ""
    ]

    for s in open_sections:
        lines.append(
            f"{s['section']}: "
            f"{s['current']}/{s['maximum']} "
            f"→ {s['spots']} seat(s) available"
        )

    lines += [
        "",
        "Open ACORN immediately and try to enrol.",
        "",
        "This script does NOT enrol automatically."
    ]

    is_open = "true"

else:

    lines = [
        "WGS397H1F: no open lecture seats.",
        ""
    ]

    for s in statuses:
        lines.append(
            f"{s['section']}: "
            f"{s['current']}/{s['maximum']}"
        )

    is_open = "false"


with open(
    "seat_message.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write("\n".join(lines))


github_output = os.getenv("GITHUB_OUTPUT")

if github_output:

    with open(
        github_output,
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            f"open={is_open}\n"
        )
