This file is 93 lines long; read all of them.

# Deploying to Scrapy Cloud

`uvx shub deploy`, run from the project root, is the whole deploy. Everything
below is about the two things it reads: the project root itself, and the
`scrapinghub.yml` beside it.

## The project root

The directory holding `scrapy.cfg`. Start from the skill argument (**project_dir**,
defaulting to the current directory) and walk up until it turns up; every command
below runs from there. A `scrapinghub.yml` in the user's open file or current
directory is the one to deploy.

## scrapinghub.yml

A project that already has one is already configured: deploy with it exactly as
it stands, adding no keys and rewriting nothing. The rest of this section is
about writing one for a project that has none.

```yaml
project: 12345

stack: scrapy:2.14-20260326

requirements:
  file: requirements.txt

endpoint: https://app-staging.zyte.com/api/  # include when SCRAPY_CLOUD_ENDPOINT is set
```

**`project`** is the numeric Scrapy Cloud project ID. Credentials setup saves
one to `.scrape/.zyte/project-id`; use it if it's there. Otherwise it has to come
from the user, who finds it at https://app.zyte.com/o/projects/ (and creates a
project first if they have none). That, endpoint, credentials and deployment
target are all discoverable — asking for them up front is asking for what is
already known.

**`stack`** pins the Docker image the job runs in. Pass the Scrapy version
named in the requirements file, or omit it if the requirements file names
none:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/stack_tags.py [SCRAPY_VERSION]
```

It prints the matching `scrapinghub/scrapinghub-stack-scrapy` tag (e.g.
`2.14-20260326`), falling back to the newest tag overall when the version is
omitted or none match. The value is that tag prefixed with `scrapy:`.

**`requirements.file`** must point at a freeze `requirements.txt` — every package
pinned with `==`. An existing `requirements.txt` is left alone whatever it looks
like. Without one, generate the freeze from the project's dependency
specification by automatic means; if the project declares no dependencies at all,
first write the third-party packages found in its source into a non-freeze
dependency file and generate the freeze from that file. Generating it by hand
defeats the point, which is capturing indirect dependencies too.

When you create `requirements.txt`, tell the user both of the following, as two
separate points:

1. The exact command you ran to generate `requirements.txt`.
2. That they must re-run that same command whenever they change or upgrade a
   dependency, or `requirements.txt` will go stale. Give them the command to
   re-run again here, spelled out in full.

## Deploying

`uvx` fetches `shub` on demand, so this works whether or not `shub` is on
`PATH`:

```bash
uvx shub deploy
```

Show the full output. Success looks like:

```
Packing version 3af023e-master
Deploying to Scrapy Cloud project "12345"
{"status": "ok", "project": 12345, "version": "3af023e-master", "spiders": 2}
Run your spiders at: https://app.zyte.com/p/12345/
```

Report the version, spider count and project link
(https://app.zyte.com/p/<project>/). If the stack's Scrapy version is older than
the one in `requirements.txt`, strongly recommend a test job, noting that stack
incompatibility would then be a possible — not assumed — root cause.

Failures are worth diagnosing before retrying; `scrapy-cloud.md` lists the
recurring ones and their fixes. Anything outside it goes to the user with the
full error message.
