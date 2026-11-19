"""Resend notifications for brand runs: one email per run, split only when the payload would exceed MAX_BYTES.

monitor.notify splits every 60 changes, which burns Resend quota; this keeps its retry and
idempotency behaviour but packs changes by measured payload size instead.
"""
import json
import os
import time

from monitor import email_body, fingerprint, request_options

MAX_BYTES = 10_000_000


def text_body(changes):
    return '\n\n'.join(f'{c["title"]}: {c["kind"]}\n{c["detail"]}\n{c["url"]}' for c in changes)


def payload_for(sender, recipients, subject, chunk, store):
    return {'from': sender, 'to': recipients, 'subject': subject,
            'html': email_body(chunk, store), 'text': text_body(chunk)}


def size_of(payload):
    return len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))


def split(changes, store, sender, recipients, max_bytes=MAX_BYTES):
    """Greedy split by payload size; a subject placeholder leaves room for the '(i/n)' suffix."""
    subject = f'{store.name}: {len(changes)} changes (999/999)'
    overhead = size_of(payload_for(sender, recipients, subject, [], store))
    empty = size_of(payload_for('', [], '', [], store))
    chunks, current, used = [], [], overhead
    for change in changes:
        cost = size_of(payload_for('', [], '', [change], store)) - empty + 4  # '\n\n' text separator, JSON-escaped
        if current and used + cost > max_bytes:
            chunks.append(current)
            current, used = [], overhead
        current.append(change)
        used += cost
    if current:
        chunks.append(current)
    return chunks


def send(api, payload, key):
    for attempt in range(4):
        response = None
        try:
            response = api.post('https://api.resend.com/emails', data=payload,
                                headers={'Idempotency-Key': key}, timeout=45000)
            if not response.ok:
                try:
                    detail = response.json().get('message', 'No error message')
                except ValueError:
                    detail = 'Non-JSON response'
                raise ValueError(f'Resend rejected email: HTTP {response.status} — {detail}')
            if not response.json().get('id'):
                raise ValueError('Resend returned no email ID')
            return
        except ValueError:
            raise
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
        finally:
            if response is not None:
                response.dispose()


def notify(playwright, changes, event_key, store, max_bytes=MAX_BYTES):
    required = {k: os.environ.get(k, '').strip() for k in ('RESEND_API_KEY', 'EMAIL_FROM', 'EMAIL_TO')}
    if not all(required.values()):
        raise ValueError('Set RESEND_API_KEY, EMAIL_FROM and EMAIL_TO before sending')
    recipients = [x.strip() for x in required['EMAIL_TO'].split(',') if x.strip()]
    if not recipients:
        raise ValueError('EMAIL_TO must contain at least one address')
    chunks = split(changes, store, required['EMAIL_FROM'], recipients, max_bytes)
    api = playwright.request.new_context(**request_options(), extra_http_headers={
        'Authorization': 'Bearer ' + required['RESEND_API_KEY']})
    try:
        for index, chunk in enumerate(chunks, 1):
            suffix = f' ({index}/{len(chunks)})' if len(chunks) > 1 else ''
            payload = payload_for(required['EMAIL_FROM'], recipients,
                                  f'{store.name}: {len(changes)} changes{suffix}', chunk, store)
            if size_of(payload) > max_bytes and len(chunk) > 1:
                raise ValueError(f'Email {index} is {size_of(payload)} bytes, over the {max_bytes} limit')
            # Stable key retries the SAME payload after send/save/push failures.
            key = store.name.lower().replace(' ', '-') + '-' + fingerprint([event_key, payload])
            send(api, payload, key)
            time.sleep(0.6)
    finally:
        api.dispose()
    return len(chunks)
