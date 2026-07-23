# Release 1.3 — Commercial Layer

## Added

- CRM profile model for each client.
- Service catalog model with default repair categories and seed items.
- Ticket service line items for quote composition.
- Catalog-driven price engine: add repair items by button and send computed price to client.
- Admin CRM card from ticket view.
- Retention reminder model and admin retention queue.
- Automatic CRM update when a ticket is marked done.
- Automatic post-repair retention reminder creation.
- Client post-repair buttons: review and repeat similar request.

## UX

The main flow remains button-first. Free text is still used only where arbitrary input is unavoidable, such as manual price/time entry.

## Database

New migration:

- `0003_v13_commercial_layer.py`

New tables:

- `client_profiles`
- `service_catalog_items`
- `ticket_service_items`
- `retention_reminders`

## Notes

Catalog seed data is created lazily by application code, not by the migration. This avoids hidden migration behavior and keeps production upgrades safer.

## Validation

```bash
python3 -m compileall app tests
pytest -q
```

Current local result:

```text
3 passed, 1 skipped
```
