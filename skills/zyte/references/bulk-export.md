This file is 22 lines long; read all of them.

# Exporting a job's items, logs or requests

The Scrapy Cloud tools of the Zyte MCP return samples, stats, log tails and
failed requests, but cap and truncate their results. A complete export goes
through `shub`, written straight to a file so that it never enters the
context:

```bash
uvx shub items PROJECT_ID/SPIDER_ID/JOB_ID > items.jsonl
uvx shub log PROJECT_ID/SPIDER_ID/JOB_ID > log.txt
uvx shub requests PROJECT_ID/SPIDER_ID/JOB_ID > requests.jsonl
```

A dashboard URL such as `https://app.zyte.com/p/12345/2/15` works in place of
the job key. Items and requests come out as JSON Lines, one per line. Search
the file afterwards instead of reading it whole, and report its path, line
count and size.

`shub` authenticates with `SHUB_APIKEY` or its own `shub login` config; on an
authentication error, follow `credentials.md`, then retry.
