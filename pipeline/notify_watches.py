"""Watchlist alerts after an ingest run.

For every change in this run to an article someone watches, write one inbox row (notifications;
unique per user and event, so re-runs never repeat an alert) and send each user one push that
summarises their new alerts. Every kind of change counts: price drop or rise, back in stock, sold
out, sale started or ended, removed from the store. Only changes from recent snapshots count
(notifiable events; a removal counts when it was seen in the last 24 hours).
"""
from pipeline import notify_run

DESCRIBE = {
    'price_drop': 'Price drop',
    'price_rise': 'Price rise',
    'back_in_stock': 'Back in stock',
    'out_of_stock': 'Sold out',
    'sale_started': 'Sale started',
    'sale_ended': 'Sale ended',
    'removed': 'Removed from the store',
    'new_product': 'Listed again',
}


def rupees(minor):
    if minor is None:
        return '—'
    whole, paisa = divmod(int(minor), 100)
    return f'PKR {whole:,}' + (f'.{paisa:02d}' if paisa else '')


def alert_text(kind, title, brand, old_value, new_value):
    old_price = (old_value or {}).get('price')
    new_price = (new_value or {}).get('price')
    line = DESCRIBE.get(kind, kind.replace('_', ' ').capitalize())
    if kind in ('price_drop', 'price_rise') and old_price and new_price is not None:
        percent = round(abs(new_price - old_price) * 100 / old_price)
        line += f' {percent}%: {rupees(old_price)} → {rupees(new_price)}'
    elif kind == 'back_in_stock' and new_price is not None:
        line += f' at {rupees(new_price)}'
    elif kind == 'sale_started' and (new_value or {}).get('discount_pct'):
        line += f', {new_value["discount_pct"]}% off'
    return f'{brand}: {title}', line


def create_alerts(conn, since):
    """Insert inbox rows for this run's changes to watched articles. Returns the new rows as
    (notification id, user id, product id, title, body)."""
    rows = conn.execute("""
        select w.user_id, e.id, e.kind, p.id, p.title, b.name, e.old_value, e.new_value
        from product_events e
        join scans s on s.id = e.scan_id
        join watches w on w.product_id = e.product_id
        join products p on p.id = e.product_id
        join brands b on b.id = p.brand_id
        where s.status = 'ok' and s.ingested_at >= %s and e.variant_id is null
          and (e.notifiable or (e.kind = 'removed' and e.observed_at > now() - interval '24 hours'))
        order by e.id""", (since,)).fetchall()
    created = []
    for user_id, event_id, kind, product_id, title, brand, old_value, new_value in rows:
        heading, body = alert_text(kind, title, brand, old_value, new_value)
        inserted = conn.execute("""
            insert into notifications (user_id, event_id, kind, title, body, deep_link, status)
            values (%s, %s, %s, %s, %s, %s, 'pending')
            on conflict (user_id, event_id) do nothing
            returning id""", (user_id, event_id, kind, heading, body, f'/product/{product_id}')).fetchone()
        if inserted:
            created.append((inserted[0], user_id, product_id, heading, body))
    return created


def push_for_user(alerts):
    """One push per user: the alert itself when there is one, a summary when there are several."""
    if len(alerts) == 1:
        _, _, product_id, heading, body = alerts[0]
        return heading, body, f'/product/{product_id}'
    titles = ', '.join(alert[3].split(': ', 1)[-1] for alert in alerts[:2])
    more = f' and {len(alerts) - 2} more' if len(alerts) > 2 else ''
    return f'{len(alerts)} watched articles changed', f'{titles}{more}.', '/watchlist'


def notify_watchers(conn, since, log=print, post=notify_run.post_json):
    alerts = create_alerts(conn, since)
    if not alerts:
        return 0
    by_user = {}
    for alert in alerts:
        by_user.setdefault(alert[1], []).append(alert)
    tokens = {}
    for user_id, token in conn.execute('select user_id, push_token from devices where user_id = any(%s)',
                                       (list(by_user),)).fetchall():
        tokens.setdefault(user_id, []).append(token)
    sent_users, gone = 0, []
    for user_id, user_alerts in by_user.items():
        ids = [alert[0] for alert in user_alerts]
        user_tokens = tokens.get(user_id, [])
        if not user_tokens:
            conn.execute("update notifications set status = 'held' where id = any(%s)", (ids,))
            continue
        title, body, path = push_for_user(user_alerts)
        sent, user_gone = notify_run.send(user_tokens, title, body, post=post, path=path)
        gone += user_gone
        status = 'sent' if sent else 'failed'
        conn.execute('update notifications set status = %s, sent_at = case when %s then now() end where id = any(%s)',
                     (status, sent > 0, ids))
        sent_users += 1 if sent else 0
    if gone:
        conn.execute('delete from devices where push_token = any(%s)', (gone,))
    log(f'watch alerts: {len(alerts)} new for {len(by_user)} account(s); pushed to {sent_users}')
    return len(alerts)
