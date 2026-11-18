#!/usr/bin/env python3
"""Save a Claude subagent's final output from its task transcript.

Usage: python3 save_output.py <transcript .output file> <target .md file>
The output is the text of the subagent's hand-back tool call or, without one, its last text message; an API error
message is never the output.
Prints only the number of characters saved, one line for a run that ended on an API error, "no output found" or the
usage, so the transcript never enters the orchestrator's context.
Exit code 1 when no output was found (also for a missing transcript); 2 on wrong usage; 3 when the run ended on an API error (a session limit, an overload): the text
before the error, if any, is saved, and the run counts as failed (tooling.md, "Failed subagents").
"""
import json
import sys


def read_entries(path):
    """Yield (line number, entry, message) for every assistant entry of the transcript."""
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    for n, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        msg = entry.get('message') or {}
        if entry.get('type') == 'assistant' and isinstance(msg.get('content'), list):
            yield n, entry, msg


def final_output(path):
    # a message may arrive as several entries with one block each, so text blocks are joined per message id
    handback, last_id, last_parts = None, None, []
    for n, entry, msg in read_entries(path):
        if entry.get('isApiErrorMessage'):
            continue
        mid = msg.get('id') or 'line-%d' % n
        for part in msg['content']:
            if part.get('type') == 'tool_use' and 'handback' in part.get('name', '').lower():
                texts = [v for v in (part.get('input') or {}).values() if isinstance(v, str)]
                if texts:
                    handback = max(texts, key=len)
            elif part.get('type') == 'text' and part.get('text', '').strip():
                if mid != last_id:
                    last_id, last_parts = mid, []
                last_parts.append(part['text'])
    return handback or ('\n\n'.join(last_parts) if last_parts else None)


def ended_on_api_error(path):
    """True when the subagent's last message is an API error: the run stopped before its final output."""
    last = None
    for _, entry, _ in read_entries(path):
        last = entry
    return bool(last and last.get('isApiErrorMessage'))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    try:
        output, failed = final_output(sys.argv[1]), ended_on_api_error(sys.argv[1])
    except FileNotFoundError:
        print('no output found: the transcript %s does not exist' % sys.argv[1])
        return 1
    if output:
        with open(sys.argv[2], 'w', encoding='utf-8') as out:
            out.write(output)
        print('saved %d characters to %s' % (len(output), sys.argv[2]))
    if failed:
        print('the run ended on an API error: it failed (tooling.md, "Failed subagents")')
        return 3
    if not output:
        print('no output found in ' + sys.argv[1])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
