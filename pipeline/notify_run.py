"""Send the "new data is in" push after an ingest run, to every phone in broadcast_devices.

Called from pipeline.ingest at the end of a run. Only runs that loaded at least one scan send a
push, and only changes from recent snapshots (notifiable events) are counted, so a backfill or a
quiet re-run never notifies. Push failures are reported but never fail the ingest.

Uses the Expo Push Service (https://exp.host/--/api/v2/push/send): no key is needed unless
"enhanced push security" is switched on in the Expo dashboard, in which case set EXPO_ACCESS_TOKEN.
"""
import json
import os
import urllib.request

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
BATCH = 100  # Expo accepts at most 100 messages per request

KIND_WORDS = (
    ('price_drop', 'price drop', 'price drops'),
    ('back_in_stock', 'back in stock', 'back in stock'),
    ('new_product', 'new', 'new'),
    ('price_rise', 'price rise', 'price rises'),
    ('out_of_stock', 'sold out', 'sold out'),
)


def run_summary(conn, since):
    """Brands loaded since `since` and their notifiable product-level changes, per kind."""
    scans = conn.execute("""select count(*), count(distinct brand_id) from scans
                            where status = 'ok' and ingested_at >= %s""", (since,)).fetchone()
    kinds = dict(conn.execute("""select e.kind, count(*) from product_events e
                                 join scans s on s.id = e.scan_id
                                 where s.status = 'ok' and s.ingested_at >= %s
                                   and e.variant_id is null and e.notifiable
                                 group by e.kind""", (since,)).fetchall())
    return {'scans': scans[0], 'brands': scans[1], 'kinds': kinds, 'total': sum(kinds.values())}


def message_text(summary):
    brands = summary['brands']
    title = 'New prices and stock are in'
    if summary['total'] == 0:
        return title, f'Checked {brands} brand{"s" if brands != 1 else ""}: no changes this time.'
    parts = []
    for kind, one, many in KIND_WORDS:
        count = summary['kinds'].get(kind, 0)
        if count:
            parts.append(f'{count:,} {one if count == 1 else many}')
    body = f'{summary["total"]:,} change{"s" if summary["total"] != 1 else ""} across {brands} ' \
           f'brand{"s" if brands != 1 else ""}'
    return title, body + (': ' + ', '.join(parts[:3]) if parts else '') + '.'


def post_json(url, payload, token=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def send(tokens, title, body, post=post_json, path='/changes'):
    """Send one message to each token. Returns (sent, gone): accepted count and tokens Expo
    reports as no longer registered (app uninstalled or notifications revoked)."""
    sent, gone = 0, []
    access = os.environ.get('EXPO_ACCESS_TOKEN') or None
    for start in range(0, len(tokens), BATCH):
        batch = tokens[start:start + BATCH]
        messages = [{'to': token, 'title': title, 'body': body, 'data': {'url': path},
                     'channelId': 'default', 'priority': 'high', 'sound': 'default'} for token in batch]
        tickets = post(EXPO_PUSH_URL, messages, access).get('data') or []
        for token, ticket in zip(batch, tickets):
            if ticket.get('status') == 'ok':
                sent += 1
            elif (ticket.get('details') or {}).get('error') == 'DeviceNotRegistered':
                gone.append(token)
    return sent, gone


def notify_after_run(conn, since, log=print, post=post_json):
    """Push a summary of this run to every registered phone. Returns the number of pushes accepted."""
    summary = run_summary(conn, since)
    if summary['scans'] == 0:
        return 0
    tokens = [row[0] for row in conn.execute('select push_token from broadcast_devices order by created_at')]
    if not tokens:
        log('push: no phones registered')
        return 0
    title, body = message_text(summary)
    sent, gone = send(tokens, title, body, post=post)
    if gone:
        conn.execute('delete from broadcast_devices where push_token = any(%s)', (gone,))
    log(f'push: "{body}" accepted for {sent} of {len(tokens)} phone(s); {len(gone)} unregistered removed')
    return sent
