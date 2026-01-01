# Echo Endpoint Tests

These tests verify the public echo API.

## Setup

- Ensure the database is migrated and seeded.
- The application must be running (or imported) for the tests to hit the endpoint.

## Tests

```javascript
import request from 'supertest';
import app from '../src/app';

describe('Public Echo Endpoint', () => {
  it('returns canonical JSON for #192', async () => {
    const res = await request(app).get('/v1/echoes/192');
    expect(res.status).toBe(200);
    expect(res.body.artifact_id).toBe(192);
  });

  it('returns 404 for non‑public echoes', async () => {
    const res = await request(app).get('/v1/echoes/999');
    expect(res.status).toBe(404);
  });
});
```

Run the suite after migration and seeding:

```bash
npm test
```